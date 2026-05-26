"""OBCD model definitions, vendored from the upstream OBCD notebooks.

Excluded from linting and type checking, treated as vendored code.
"""

import torch
import torch.nn as nn
from torchvision.ops import roi_align

# Import YOLO from the submodule, as top-level import fails mypy strict mode.
from ultralytics.models import YOLO

_MATCH_THRESHOLD = 10.0
_ROI_SIZE = (32, 32)


def extract_features(image, rois, feature_extractor):
    """Extracts features for the ROIs from the image."""
    aligned = roi_align(image, rois, output_size=_ROI_SIZE)
    features = feature_extractor(aligned)  # Extract features
    features = features.view(features.size(0), -1)  # Flatten features
    return features  # Shape: [num_rois, 3072]


def match_features(features1, features2, rois1, rois2, threshold=_MATCH_THRESHOLD):
    """Matches features between two sets using Euclidean distance."""
    batch_indices1 = rois1[:, 0].long()
    batch_indices2 = rois2[:, 0].long()

    matched_indices1, matched_indices2 = [], []
    unmatched_indices1, unmatched_indices2 = [], []

    for batch_idx in torch.unique(batch_indices1).tolist():
        f1 = features1[batch_indices1 == batch_idx]
        f2 = features2[batch_indices2 == batch_idx]

        if f1.size(0) == 0 or f2.size(0) == 0:
            unmatched_indices1.extend((batch_idx, i) for i in range(f1.size(0)))
            unmatched_indices2.extend((batch_idx, i) for i in range(f2.size(0)))
            continue

        # Compute pairwise Euclidean distances
        dists = torch.cdist(f1, f2)
        matches = dists <= threshold

        matched_1 = matches.any(dim=1).nonzero(as_tuple=True)[0].tolist()
        matched_2 = matches.any(dim=0).nonzero(as_tuple=True)[0].tolist()

        unmatched_1 = (~matches.any(dim=1)).nonzero(as_tuple=True)[0].tolist()
        unmatched_2 = (~matches.any(dim=0)).nonzero(as_tuple=True)[0].tolist()

        matched_indices1.extend((batch_idx, i) for i in matched_1)
        matched_indices2.extend((batch_idx, i) for i in matched_2)
        unmatched_indices1.extend((batch_idx, i) for i in unmatched_1)
        unmatched_indices2.extend((batch_idx, i) for i in unmatched_2)

    return matched_indices1, matched_indices2, unmatched_indices1, unmatched_indices2


def batch_and_pad(features, metadata, matched_indices, unmatched_indices, padding_size):
    """Batch and pad features and metadata based on matched/unmatched indices."""
    batch_size = len(torch.unique(metadata[:, 0]))
    num_features = features.size(1)

    # Matched
    matched_features = torch.zeros((batch_size, padding_size, num_features), device=features.device)
    matched_metadata = torch.zeros((batch_size, padding_size, metadata.size(1) - 1), device=metadata.device)
    matched_metadata[:, :, 1] = 1  # Padding with [0, 1, 0, 0, 0, 0, 0]

    for batch_idx in range(batch_size):
        batch_matches = [i for i, (b, _) in enumerate(matched_indices) if b == batch_idx]
        num_matches = len(batch_matches)

        matched_features[batch_idx, :num_matches, :] = features[batch_matches, :]
        matched_metadata[batch_idx, :num_matches, :] = metadata[batch_matches, 1:]  # Exclude batch_idx

    # Unmatched
    unmatched_features = torch.zeros((batch_size, padding_size, num_features), device=features.device)
    unmatched_metadata = torch.zeros((batch_size, padding_size, metadata.size(1) - 1), device=metadata.device)
    unmatched_metadata[:, :, 1] = 1  # Padding with [0, 1, 0, 0, 0, 0, 0]

    for batch_idx in range(batch_size):
        batch_unmatches = [i for i, (b, _) in enumerate(unmatched_indices) if b == batch_idx]
        num_unmatches = len(batch_unmatches)

        unmatched_features[batch_idx, :num_unmatches, :] = features[batch_unmatches, :]
        unmatched_metadata[batch_idx, :num_unmatches, :] = metadata[batch_unmatches, 1:]

    return matched_features, unmatched_features, matched_metadata, unmatched_metadata


def calculate_max_objects_from_rois(rois1, rois2):
    """Return the largest object count across both frames' batch items."""
    # Count occurrences of batch_idx in both rois1 and rois2
    counts1 = torch.bincount(rois1[:, 0].long())
    counts2 = torch.bincount(rois2[:, 0].long())

    # Find the maximum number of objects in any batch
    max_objects1 = counts1.max().item() if counts1.numel() > 0 else 0
    max_objects2 = counts2.max().item() if counts2.numel() > 0 else 0

    return max(max_objects1, max_objects2)


def process_pipeline(
    image1,
    rois1,
    image2,
    rois2,
    metadata1,
    metadata2,
    feature_extractor,
    threshold=_MATCH_THRESHOLD,
):
    """Full pipeline to extract features, match them, and batch and pad the data."""
    # Extract features
    features1 = extract_features(image1, rois1, feature_extractor)
    features2 = extract_features(image2, rois2, feature_extractor)

    # Match features
    matched_indices1, matched_indices2, unmatched_indices1, unmatched_indices2 = match_features(
        features1, features2, rois1, rois2, threshold)

    # Find max padding size
    max_objects = calculate_max_objects_from_rois(rois1, rois2)

    # Batch and pad
    matched_features1, unmatched_features1, matched_metadata1, unmatched_metadata1 = batch_and_pad(
        features1, metadata1, matched_indices1, unmatched_indices1, max_objects)

    matched_features2, unmatched_features2, matched_metadata2, unmatched_metadata2 = batch_and_pad(
        features2, metadata2, matched_indices2, unmatched_indices2, max_objects)

    return (
        matched_features1, matched_features2, unmatched_features1, unmatched_features2,
        matched_metadata1, matched_metadata2, unmatched_metadata1, unmatched_metadata2, max_objects,
        unmatched_indices1, unmatched_indices2,
    )


def joint_normalize_min_max(metadata1, metadata2):
    """Normalize two datasets together using Min-Max normalization."""
    # Concatenate both datasets along the batch dimension
    combined_data = torch.cat((metadata1, metadata2), dim=0)

    # Calculate min and max across combined data
    min_vals = torch.min(combined_data, dim=0, keepdim=True)[0]
    max_vals = torch.max(combined_data, dim=0, keepdim=True)[0]

    # Avoid division by zero
    range_vals = max_vals - min_vals
    range_vals[range_vals == 0] = 1.0

    # Normalize both datasets
    normalized_metadata1 = (metadata1 - min_vals) / range_vals
    normalized_metadata2 = (metadata2 - min_vals) / range_vals

    return normalized_metadata1, normalized_metadata2


def _extract_change_bboxes(
    rois1, rois2, per_object_metadata1, per_object_metadata2,
    unmatched_indices1, unmatched_indices2,
    width, height, names,
):
    """Return normalized (x1, y1, x2, y2, label) tuples for unmatched ROIs in batch zero.

    Unmatched ROIs cover new and vanished detections. The dummy [0, 0, 1, 1] placeholder 
    ROI emitted for empty frames is filtered.
    """
    bboxes: list[tuple[float, float, float, float, str]] = []
    pairs = (
        (rois1, per_object_metadata1, unmatched_indices1),
        (rois2, per_object_metadata2, unmatched_indices2),
    )
    for rois, per_object_metadata, unmatched_indices in pairs:
        local_indices = [local_idx for batch_idx, local_idx in unmatched_indices if batch_idx == 0]
        if not local_indices:
            continue
        mask = rois[:, 0] == 0
        boxes = rois[mask][local_indices, 1:].detach().cpu().tolist()
        classes = per_object_metadata[mask, 2][local_indices].long().detach().cpu().tolist()
        for box, cls_idx in zip(boxes, classes, strict=True):
            if box == [0.0, 0.0, 1.0, 1.0]:
                continue
            label = names.get(cls_idx, "object")
            x1, y1, x2, y2 = box
            bboxes.append((x1 / width, y1 / height, x2 / width, y2 / height, label))
    return tuple(bboxes)


class ConvOBCDModel(nn.Module):
    """Conv+FC change-detection network."""

    def __init__(
        self,
        feature_extractor: nn.Module,
        yolo_model: YOLO,
        num_classes: int,
        device: torch.device,
        feature_dim: int = 256,
    ) -> None:
        super().__init__()

        self.feature_extractor = feature_extractor
        self.yolo_model = yolo_model
        self.num_classes = num_classes
        self.device = device  # Device for tensor operations (e.g., 'cuda' or 'cpu')

        # Update metadata_dim based on the new structure
        self.metadata_dim = (9 + num_classes)  # (9 + num_classes) (whole-image metadata)
        self.feature_dim = feature_dim
        self.yolo_cache = {}  # Cache for YOLO results
        self.padding_size = 1

        # Metadata processing branch
        self.whole_metadata_fc = nn.Sequential(
            nn.Linear(self.metadata_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64)
        ).to(self.device)

        self.metadata_fc = nn.Sequential(
            nn.Linear(7, 128),
            nn.BatchNorm1d(7),
            nn.ReLU(),
            nn.Linear(128, 64),
        ).to(self.device)

        self.spatial_fc = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=1, padding=1),  # Conv2D for spatial processing
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2),  # Downsample spatial dimensions
            nn.Flatten(start_dim=1),  # Flatten spatial dimensions
            nn.Linear(32 * 16 * 16, 128),  # Map spatial features to 128-dim vector
            nn.ReLU()
        )

        # Sequence-Aware Fully Connected Layer
        self.temporal_fc = nn.Sequential(
            nn.Linear(128, 128),  # Process each timestep independently
            nn.ReLU(),
            nn.Dropout(0.5)
        )

        # Temporal Aggregation + Final Output
        self.feature_fc = nn.Sequential(
            nn.Linear(128 * self.padding_size, 128),  # Aggregate features across the sequence
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, 64)  # Map to final output dimension
        )

        self.unmatched_metadata_fc = nn.Sequential(
            nn.Linear(7, 128),
            nn.ReLU(),
            nn.Linear(128, 64)
        ).to(self.device)

        # Combined classifier
        self.combined_fc = nn.Sequential(
            nn.Linear(320, 128),  # Combine feature + metadata branches
            nn.ReLU(),
            nn.Linear(128, 1),  # Binary classification: change or no change
            #nn.Sigmoid()  # Output a probability of change
        ).to(self.device)

        # Ensure the model components are moved to the correct device (usually handled in the forward pass)
        self.to(self.device)

    def extract_metadata(self, results, yolo_num_classes):
        """Extracts per-object and whole-image metadata for an entire batch of images.

        Automatically assigns batch indices to the ROIs.
        """
        C = yolo_num_classes  # Maximum YOLO class index + 1
        batch_size = len(results)
        device = self.device

        rois_batch = []
        per_object_metadata = []
        whole_image_metadata = []

        for batch_idx in range(batch_size):
            result = results[batch_idx]  # YOLO result for this image
            if hasattr(result, 'boxes') and len(result.boxes) > 0:
                boxes = result.boxes.xyxy  # Bounding boxes (x1, y1, x2, y2)
                class_labels = result.boxes.cls.to(device).tolist()  # Class labels
                num_objects = len(class_labels)

                # Whole-image metadata (initialize accumulators)
                class_frequency = torch.zeros(C, device=device)  # Class distribution vector
                widths, heights = [], []
                x_centers, y_centers = [], []

                for box, cls in zip(boxes, class_labels):
                    # Per-object metadata
                    x1, y1, x2, y2 = box.tolist()
                    width = x2 - x1
                    height = y2 - y1
                    aspect_ratio = width / height if height > 0 else 0
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2

                    rois_batch.append([batch_idx, x1, y1, x2, y2])  # ROI with batch index
                    per_object_metadata.append(torch.tensor(
                        [batch_idx, 1, cls, center_x, center_y, width, height, aspect_ratio],
                        device=device
                    ))

                    # Accumulate for whole-image metadata
                    class_frequency[int(cls)] += 1
                    widths.append(width)
                    heights.append(height)
                    x_centers.append(center_x)
                    y_centers.append(center_y)

                if len(widths) > 1:
                    mean_width = torch.tensor(widths).mean().item()
                    std_width = torch.tensor(widths).std().item()
                    mean_height = torch.tensor(heights).mean().item()
                    std_height = torch.tensor(heights).std().item()
                    mean_x_center = torch.tensor(x_centers).mean().item()
                    std_x_center = torch.tensor(x_centers).std().item()
                    mean_y_center = torch.tensor(y_centers).mean().item()
                    std_y_center = torch.tensor(y_centers).std().item()
                else:
                    mean_width, std_width = widths[0], 0
                    mean_height, std_height = heights[0], 0
                    mean_x_center, std_x_center = x_centers[0], 0
                    mean_y_center, std_y_center = y_centers[0], 0

                whole_image_metadata.append(torch.cat([
                    torch.tensor([num_objects, mean_width, std_width, mean_height, std_height, mean_x_center, std_x_center, mean_y_center, std_y_center], device=device),
                    class_frequency
                ]))
            else:
                # No objects detected
                rois_batch.append([batch_idx, 0, 0, 1, 1])  # Dummy ROI
                per_object_metadata.append(torch.tensor(
                    [batch_idx, 0, C, 0, 0, 0, 0, 0], device=device
                ))  # Dummy per-object metadata
                # Whole-image metadata for "no objects"
                whole_image_metadata.append(torch.cat([
                    torch.zeros(9, device=device),  # No statistics
                    torch.zeros(C, device=device)  # Empty class distribution
                ]))

        # Combine per-object metadata into a single tensor
        per_object_metadata = torch.stack(per_object_metadata, dim=0)
        # Combine ROIs into a single tensor
        rois_batch = torch.tensor(rois_batch, dtype=torch.float, device=device)
        # Combine whole-image metadata into a single tensor (one per image)
        whole_image_metadata = torch.stack(whole_image_metadata, dim=0)

        return per_object_metadata, whole_image_metadata, rois_batch

    def forward(self, image1, image2):
        """Forward pass for change detection between two images."""
        # Get YOLO results for both images
        results1 = self.yolo_model(image1, verbose=False)
        results2 = self.yolo_model(image2, verbose=False)

        # Extract metadata and ROIs
        per_object_metadata1, whole_metadata1, rois1 = self.extract_metadata(results1, self.num_classes)
        per_object_metadata2, whole_metadata2, rois2 = self.extract_metadata(results2, self.num_classes)

        matched_features1, matched_features2, unmatched_features1, unmatched_features2, \
        matched_metadata1, matched_metadata2, unmatched_metadata1, unmatched_metadata2, padding_size, \
        unmatched_indices1, unmatched_indices2 \
        = process_pipeline(
            image1,
            rois1,
            image2,
            rois2,
            per_object_metadata1,
            per_object_metadata2,
            self.feature_extractor,
        )

        matched_metadata_diff = torch.abs(matched_metadata1 - matched_metadata2)
        matched_feature_diff = torch.abs(matched_features1 - matched_features2)

        self.padding_size = padding_size

        #self.feature_fc[4] = nn.Linear(3072 * self.padding_size, 128).to(self.device)
        self.metadata_fc[1] = nn.BatchNorm1d(padding_size).to(self.device)
        matched_metadata_out = self.metadata_fc(matched_metadata_diff)
        matched_feature_diff = matched_feature_diff.view(matched_feature_diff.size(0), 3, padding_size, 32, 32)
        matched_feature_diff = matched_feature_diff.permute(0, 2, 1, 3, 4)
        matched_feature_diff = matched_feature_diff.reshape(matched_feature_diff.size(0)*padding_size, 3, 32, 32)  # Restore spatial structure

        # matched_feature_out = self.feature_fc(matched_feature_diff)
        matched_feature_out = self.spatial_fc(matched_feature_diff)
        matched_feature_out = self.temporal_fc(matched_feature_out)
        matched_feature_out = matched_feature_out.view(image1.size(0), padding_size, -1)
        self.feature_fc[0] = nn.Linear(128, 128).to(self.device)
        matched_feature_out = self.feature_fc(matched_feature_out)

        whole_metadata1, whole_metadata2 = joint_normalize_min_max(whole_metadata1, whole_metadata2)

        # Whole-image metadata difference
        whole_metadata_diff = torch.abs(whole_metadata1 - whole_metadata2)
        whole_metadata_out = self.whole_metadata_fc(whole_metadata_diff)  # Single vector
        matched_metadata_out = matched_metadata_out.view(matched_metadata_out.size(0), -1)  # Flatten extra dimensions
        matched_feature_out = matched_feature_out.view(matched_feature_out.size(0), -1)  # Flatten extra dimensions
        unmatched_metadata_out1 = self.unmatched_metadata_fc(unmatched_metadata1)
        unmatched_metadata_out1 = unmatched_metadata_out1.view(unmatched_metadata_out1.size(0), -1)  # Flatten extra dimensions
        unmatched_metadata_out2 = self.unmatched_metadata_fc(unmatched_metadata2)
        unmatched_metadata_out2 = unmatched_metadata_out2.view(unmatched_metadata_out2.size(0), -1)  # Flatten extra dimensions
        combined_input = torch.cat([matched_metadata_out, matched_feature_out, whole_metadata_out, unmatched_metadata_out1, unmatched_metadata_out2], dim=1).to(self.device)
        combined_feature_size = combined_input.size(1)
        self.combined_fc[0] = nn.Linear(combined_feature_size, 128).to(self.device)
        change_prob = self.combined_fc(combined_input)
        change_prob = torch.sigmoid(change_prob)

        change_bboxes = _extract_change_bboxes(
            rois1, rois2, per_object_metadata1, per_object_metadata2,
            unmatched_indices1, unmatched_indices2,
            float(image1.shape[-1]), float(image1.shape[-2]),
            self.yolo_model.names,
        )
        return change_prob, change_bboxes

    def set_train(self) -> None:
        """Put the trainable submodules into training mode."""
        # Set only the ConvOBCDModel-specific layers to training mode
        self.metadata_fc.train()
        self.feature_fc.train()
        self.combined_fc.train()
        self.whole_metadata_fc.train()

        # Ensure YOLO and feature extractor layers remain frozen (don't change their state)
        for param in self.yolo_model.parameters():
            param.requires_grad = False
        for param in self.feature_extractor.parameters():
            param.requires_grad = False

    def set_eval(self) -> None:
        """Put the trainable submodules into evaluation mode."""
        # Set only the ConvOBCDModel-specific layers to evaluation mode
        self.metadata_fc.eval()
        self.feature_fc.eval()
        self.combined_fc.eval()
        self.whole_metadata_fc.eval()
        self.feature_extractor.eval()


class TransOBCDModel(nn.Module):
    """Transformer change-detection network."""

    def __init__(
        self,
        feature_extractor: nn.Module,
        yolo_model: YOLO,
        num_classes: int,
        device: torch.device,
        feature_dim: int = 3072,
        metadata_dim: int = 7,
        max_objects: int = 10,
    ) -> None:
        super().__init__()

        self.feature_extractor = feature_extractor
        self.yolo_model = yolo_model
        self.num_classes = num_classes
        self.device = device
        self.feature_dim = feature_dim
        self.metadata_dim = metadata_dim
        self.max_objects = max_objects  # Default value, can be updated when loading checkpoint
        self.whole_metadata_dim = 9 + num_classes
        self.d_model = 128

        for param in self.feature_extractor.parameters():
            param.requires_grad = False
        for param in self.yolo_model.parameters():
            param.requires_grad = False

        self.feature_embed = nn.Linear(feature_dim, self.d_model)
        self.metadata_embed = nn.Linear(metadata_dim, self.d_model)
        self.whole_metadata_embed = nn.Linear(self.whole_metadata_dim, self.d_model)

        # Initialize pos_encoding with current max_objects
        self.pos_encoding = nn.Parameter(torch.zeros(1, self.max_objects, self.d_model).to(device))

        matched_encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.d_model,
            nhead=4,
            dim_feedforward=self.d_model * 4,
            dropout=0.1,
            batch_first=True
        )
        # enable_nested_tensor=False: MPS lacks the kernel, and the optimization
        # is negligible at OBCD sequence lengths (<= ~10 objects).
        self.matched_transformer = nn.TransformerEncoder(
            matched_encoder_layer, num_layers=2, enable_nested_tensor=False
        )

        unmatched_encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.d_model,
            nhead=4,
            dim_feedforward=self.d_model * 4,
            dropout=0.1,
            batch_first=True
        )
        self.unmatched_transformer = nn.TransformerEncoder(
            unmatched_encoder_layer, num_layers=2, enable_nested_tensor=False
        )

        self.combined_fc = nn.Sequential(
            nn.Linear(self.d_model * 5, self.d_model),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(self.d_model, 1),
            nn.Sigmoid()
        )

        self.to(device)

    def extract_metadata(self, results, yolo_num_classes):
        """Build per-object and whole-image metadata plus ROIs for a batch."""
        # [Unchanged from previous implementation]
        C = yolo_num_classes
        batch_size = len(results)
        device = self.device

        rois_batch = []
        per_object_metadata = []
        whole_image_metadata = []

        for batch_idx in range(batch_size):
            result = results[batch_idx]
            if hasattr(result, 'boxes') and len(result.boxes) > 0:
                boxes = result.boxes.xyxy
                class_labels = result.boxes.cls.to(device).tolist()
                num_objects = len(class_labels)

                class_frequency = torch.zeros(C, device=device)
                widths, heights = [], []
                x_centers, y_centers = [], []

                for box, cls in zip(boxes, class_labels):
                    x1, y1, x2, y2 = box.tolist()
                    width = x2 - x1
                    height = y2 - y1
                    aspect_ratio = width / height if height > 0 else 0
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2

                    rois_batch.append([batch_idx, x1, y1, x2, y2])
                    per_object_metadata.append(torch.tensor(
                        [batch_idx, 1, cls, center_x, center_y, width, height, aspect_ratio],
                        device=device
                    ))

                    class_frequency[int(cls)] += 1
                    widths.append(width)
                    heights.append(height)
                    x_centers.append(center_x)
                    y_centers.append(center_y)

                if len(widths) > 1:
                    mean_width = torch.tensor(widths).mean().item()
                    std_width = torch.tensor(widths).std().item()
                    mean_height = torch.tensor(heights).mean().item()
                    std_height = torch.tensor(heights).std().item()
                    mean_x_center = torch.tensor(x_centers).mean().item()
                    std_x_center = torch.tensor(x_centers).std().item()
                    mean_y_center = torch.tensor(y_centers).mean().item()
                    std_y_center = torch.tensor(y_centers).std().item()
                else:
                    mean_width, std_width = widths[0], 0
                    mean_height, std_height = heights[0], 0
                    mean_x_center, std_x_center = x_centers[0], 0
                    mean_y_center, std_y_center = y_centers[0], 0

                whole_image_metadata.append(torch.cat([
                    torch.tensor([num_objects, mean_width, std_width, mean_height, std_height,
                                mean_x_center, std_x_center, mean_y_center, std_y_center], device=device),
                    class_frequency
                ]))
            else:
                rois_batch.append([batch_idx, 0, 0, 1, 1])
                per_object_metadata.append(torch.tensor(
                    [batch_idx, 0, C, 0, 0, 0, 0, 0], device=device
                ))
                whole_image_metadata.append(torch.cat([
                    torch.zeros(9, device=device),
                    torch.zeros(C, device=device)
                ]))

        per_object_metadata = torch.stack(per_object_metadata, dim=0)
        rois_batch = torch.tensor(rois_batch, dtype=torch.float, device=device)
        whole_image_metadata = torch.stack(whole_image_metadata, dim=0)

        return per_object_metadata, whole_image_metadata, rois_batch

    def process_features(self, features, metadata, type='matched'):
        """Embed, position-encode, mask, and pool one object set."""
        feature_embed = self.feature_embed(features)
        metadata_embed = self.metadata_embed(metadata)
        combined = feature_embed + metadata_embed

        seq_len = combined.size(1)
        if seq_len > self.pos_encoding.size(1):
            self.pos_encoding = nn.Parameter(torch.zeros(1, seq_len, self.d_model).to(self.device))
            self.max_objects = seq_len
        combined = combined + self.pos_encoding[:, :seq_len, :]

        mask = (metadata.sum(dim=-1) == 0).float()
        mask = mask.masked_fill(mask == 1, float('-inf')).masked_fill(mask == 0, 0)

        transformer = self.matched_transformer if type == 'matched' else self.unmatched_transformer
        output = transformer(combined, src_key_padding_mask=mask)

        return output.mean(dim=1)

    def forward(self, image1, image2):
        """Return the change probability for an image pair."""
        results1 = self.yolo_model(image1, verbose=False)
        results2 = self.yolo_model(image2, verbose=False)

        per_object_metadata1, whole_metadata1, rois1 = self.extract_metadata(results1, self.num_classes)
        per_object_metadata2, whole_metadata2, rois2 = self.extract_metadata(results2, self.num_classes)

        matched_features1, matched_features2, unmatched_features1, unmatched_features2, \
        matched_metadata1, matched_metadata2, unmatched_metadata1, unmatched_metadata2, padding_size, \
        unmatched_indices1, unmatched_indices2 \
        = process_pipeline(
            image1,
            rois1,
            image2,
            rois2,
            per_object_metadata1,
            per_object_metadata2,
            self.feature_extractor,
        )

        if padding_size > self.max_objects:
            self.pos_encoding = nn.Parameter(torch.zeros(1, padding_size, self.d_model).to(self.device))
            self.max_objects = padding_size

        matched_rep1 = self.process_features(matched_features1, matched_metadata1, 'matched')
        matched_rep2 = self.process_features(matched_features2, matched_metadata2, 'matched')
        unmatched_rep1 = self.process_features(unmatched_features1, unmatched_metadata1, 'unmatched')
        unmatched_rep2 = self.process_features(unmatched_features2, unmatched_metadata2, 'unmatched')

        whole_metadata_diff = torch.abs(whole_metadata1 - whole_metadata2)
        whole_rep = self.whole_metadata_embed(whole_metadata_diff)

        combined = torch.cat([matched_rep1, matched_rep2, unmatched_rep1, unmatched_rep2, whole_rep], dim=-1)
        change_prob = self.combined_fc(combined)

        change_bboxes = _extract_change_bboxes(
            rois1, rois2, per_object_metadata1, per_object_metadata2,
            unmatched_indices1, unmatched_indices2,
            float(image1.shape[-1]), float(image1.shape[-2]),
            self.yolo_model.names,
        )
        return change_prob, change_bboxes

    def set_train(self) -> None:
        """Put the trainable submodules into training mode."""
        self.feature_embed.train()
        self.metadata_embed.train()
        self.whole_metadata_embed.train()
        self.matched_transformer.train()
        self.unmatched_transformer.train()
        self.combined_fc.train()

    def set_eval(self) -> None:
        """Put the trainable submodules into evaluation mode."""
        self.feature_embed.eval()
        self.metadata_embed.eval()
        self.whole_metadata_embed.eval()
        self.matched_transformer.eval()
        self.unmatched_transformer.eval()
        self.combined_fc.eval()
