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
import sparse_operation_kit as sok


def test():
    v1 = sok.DynamicVariable(dimension=3, initializer="17")
    v2 = sok.DynamicVariable(dimension=5, initializer="13")
    key_recv = tf.convert_to_tensor([0, 1, 1, 0, 1], dtype=tf.int64)
    offset_recv = tf.convert_to_tensor([1, 2, 1, 1], dtype=tf.int32)
    output1, output2, output3 = sok.raw_ops.lookup_forward_dynamic(
        [v1.handle, v2.handle],
        key_recv,
        offset_recv,
        hotness=[2, 2],
        rank=1,
        num_ranks=2,
        id_in_local_rank=0,
        num_gpus=2,
        combiners=["sum", "sum"],
        shard=[-1, -1],
        dimensions=[3, 5],
    )

    assert len(output1) == 2
    assert len(output1[0] == 8)
    assert len(output1[1] == 8)
    for i, item in enumerate([0.0, 0.0, 0.0, 26.0, 26.0, 26.0, 26.0, 26.0]):
        assert output1[0][i] == item
    for i, item in enumerate([0.0, 0.0, 0.0, 13.0, 13.0, 13.0, 13.0, 13.0]):
        assert output1[1][i] == item

    assert len(output2) == 3
    for i, item in enumerate([1, 1, 1]):
        assert output2[i] == item

    assert len(output3) == 5
    for i, item in enumerate([0, 0, 0, 2, 3]):
        assert output3[i] == item


if __name__ == "__main__":
    op_name = "lookup_forward_dynamic"
    if not hasattr(sok.raw_ops, op_name):
        raise RuntimeError("There is no op called " + op_name)

    test()

    print("[SOK INFO] Test of %s passed." % (op_name))
