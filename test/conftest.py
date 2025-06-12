# Copyright 2025 OpenC3, Inc.
# All Rights Reserved.
#
# This program is only licensed for use by the University of Colorado LASP

import sys
import os

# Add the project lib directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lib_path = os.path.join(project_root, 'lib')
sys.path.insert(0, lib_path)

# Add the OpenC3 cosmos python directory to Python path
cosmos_python_path = os.path.join(project_root, '..', 'cosmos', 'openc3', 'python')
if os.path.exists(cosmos_python_path):
    sys.path.insert(0, cosmos_python_path)
else:
    print(f"Warning: OpenC3 cosmos python path not found at {cosmos_python_path}")