# OBCD Pilot
A standalone desktop application that pilots the Object-Based Change Detection (OBCD) pilepine.

# What is OBCD?
Object-Based Change Detection is a computer vision system that detects whether objects in a scene have been added, removed, or swapped between two images or video frames. 

The core pipeline uses YOLOv8 for object detection and segmentation, MobileNetV2 for feature extraction, and two custom neural architectures (TransOBCD using transformers ConvOBCD using CNNs) for change classification.