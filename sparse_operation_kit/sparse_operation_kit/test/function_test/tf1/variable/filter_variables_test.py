"""
 Copyright (c) 2022, NVIDIA CORPORATION.
 
 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at
 
     http://www.apache.org/licenses/LICENSE-2.0
 
 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

import numpy as np
import tensorflow as tf
import horovod.tensorflow as hvd

import sparse_operation_kit as sok


if __name__ == "__main__":
    config = tf.compat.v1.ConfigProto()
    config.gpu_options.allow_growth = True
    sess = tf.compat.v1.Session(config=config)

    hvd.init()
    sok.init()

    v1 = tf.Variable([[0, 1, 2]])
    v2 = sok.Variable([[3, 4, 5]])
    v3 = sok.Variable([[6, 7, 8]], mode="localized:0")
    v4 = sok.DynamicVariable(dimension=3, initializer="13")
    init_op = tf.compat.v1.global_variables_initializer()
    sess.run(init_op)

    sok_vars, other_vars = sess.run(sok.filter_variables([v1, v2, v3, v4]))
    assert len(sok_vars) == 3
    assert len(other_vars) == 1

    print("[SOK INFO] filter_variables test passed")
