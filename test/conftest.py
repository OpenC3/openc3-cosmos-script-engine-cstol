# Copyright 2025 OpenC3, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
#
# CSTOL language originally developed by the University of Colorado / LASP.

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