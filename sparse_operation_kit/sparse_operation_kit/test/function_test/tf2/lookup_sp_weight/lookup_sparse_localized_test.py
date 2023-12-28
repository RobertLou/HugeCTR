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

import time
import numpy as np
import tensorflow as tf
import horovod.tensorflow as hvd

import sparse_operation_kit as sok


if __name__ == "__main__":
    hvd.init()
    gpus = tf.config.experimental.list_physical_devices("GPU")
    for gpu in gpus:
        tf.config.experimental.set_memory_growth(gpu, True)
    if gpus:
        tf.config.experimental.set_visible_devices(gpus[hvd.local_rank()], "GPU")
    sok.init()

    gpu_num = hvd.size()
    rows = [65536] * gpu_num
    cols = [128 - 8 * x for x in range(gpu_num)]
    hotness = np.random.randint(1, 10, gpu_num)
    combiners = ["mean"] * np.floor(gpu_num / 2).astype(np.int32) + ["sum"] * np.ceil(
        gpu_num - gpu_num / 2
    ).astype(np.int32)
    batch_size = 65536
    iters = 100
    gpus = np.arange(gpu_num)

    # initial value of embedding table
    weights = []
    for i in range(len(rows)):
        weight = np.random.rand(rows[i], cols[i]).astype(np.float32)
        weight = tf.convert_to_tensor(weight, dtype=tf.float32)
        # make sure the weight is same on each rank
        weight = hvd.allreduce(weight)
        weights.append(weight)

    # sok variables
    sok_vars = []
    if len(gpus) >= 2:
        for i, w in enumerate(weights):
            v = sok.Variable(w, mode="localized:%d" % gpus[i])
            sok_vars.append(v)

    else:
        for i, w in enumerate(weights):
            v = sok.Variable(w, mode="localized:0")
            sok_vars.append(v)

    local_indices = []
    for i, row in enumerate(rows):
        if hvd.rank() == gpus[i]:
            indices = np.arange(row)
            indices = tf.convert_to_tensor(indices, dtype=tf.int64)
            local_indices.append(indices)
        else:
            local_indices.append(None)

    # indices
    # sp_weights
    total_indices = []
    total_sp_weights = []
    for i in range(len(rows)):
        offsets = np.random.randint(1, hotness[i] + 1, iters * batch_size)
        offsets = tf.convert_to_tensor(offsets, dtype=tf.int64)
        offsets = hvd.broadcast(offsets, root_rank=0)
        values = np.random.randint(0, rows[i], tf.reduce_sum(offsets))
        values = tf.convert_to_tensor(values, dtype=tf.int64)
        values = hvd.broadcast(values, root_rank=0)
        sp_weights = np.random.randn(tf.reduce_sum(offsets))
        sp_weights = tf.convert_to_tensor(sp_weights, dtype=tf.float32)
        sp_weights = hvd.broadcast(sp_weights, root_rank=0)
        total_indices.append(tf.RaggedTensor.from_row_lengths(values, offsets))
        total_sp_weights.append(tf.RaggedTensor.from_row_lengths(sp_weights, offsets))

    left = batch_size // hvd.size() * hvd.rank()
    right = batch_size // hvd.size() * (hvd.rank() + 1)

    # initialize optimizer
    optimizer = tf.keras.optimizers.SGD(learning_rate=1.0)

    def step(params, indices, sp_weights):
        with tf.GradientTape() as tape:
            embeddings = sok.lookup_sparse(
                params, indices, sp_weights=sp_weights, combiners=combiners
            )
            loss = 0
            for i in range(len(embeddings)):
                loss = loss + tf.reduce_sum(embeddings[i])
        grads = tape.gradient(loss, params)
        optimizer.apply_gradients(zip(grads, params))
        loss = hvd.allreduce(loss, op=hvd.Sum)
        return loss

    # Do training
    loss1 = []
    ts = []
    t = time.time()
    for i in range(iters):
        ts.append(time.time() - t)
        t = time.time()
        indices = []
        iter_sp_weights = []
        for j in range(len(total_indices)):
            indices.append(total_indices[j][i * batch_size + left : i * batch_size + right])
            iter_sp_weights.append(
                total_sp_weights[j][i * batch_size + left : i * batch_size + right]
            )
        loss = step(sok_vars, indices, iter_sp_weights)

        loss1.append(loss)
        print("-" * 30 + "iteration %d" % i + "-" * 30)
        print("loss:", loss)
    out1 = sok_vars

    @tf.function
    def step2(params, indices, sp_weights):
        with tf.GradientTape() as tape:
            loss = 0
            for i in range(len(params)):
                embedding = tf.nn.embedding_lookup_sparse(
                    params[i], indices[i], sp_weights[i], combiner=combiners[i]
                )
                loss = loss + tf.reduce_sum(embedding)
        grads = tape.gradient(loss, params)
        grads = [hvd.allreduce(grad, op=hvd.Sum) for grad in grads]
        optimizer.apply_gradients(zip(grads, params))
        loss = hvd.allreduce(loss, op=hvd.Sum)
        return loss

    loss2 = []
    tf_vars = [tf.Variable(w) for w in weights]
    for i in range(iters):
        indices = []
        iter_sp_weights = []
        for j in range(len(total_indices)):
            indices.append(
                total_indices[j][i * batch_size + left : i * batch_size + right].to_sparse()
            )
            iter_sp_weights.append(
                total_sp_weights[j][i * batch_size + left : i * batch_size + right].to_sparse()
            )

        loss = step2(tf_vars, indices, iter_sp_weights)
        loss2.append(loss)
        print("-" * 30 + "iteration %d" % i + "-" * 30)
        print("tf loss:", loss)
    out2 = []
    for i, v in enumerate(tf_vars):
        if hvd.rank() == gpus[i]:
            out2.append(v)
        else:
            out2.append(None)

    # Check results
    diff = 0
    for i in range(len(out1)):
        if hvd.rank() == gpus[i]:
            length = tf.reduce_sum(out1[i] ** 2 + out2[i] ** 2 + 1e-8)
            diff = diff + tf.reduce_max((out1[i] - out2[i]) ** 2 / length)
    print("[SOK INFO] diff:", diff)
    assert diff < 1e-4

    diff = 0
    for i in range(iters):
        # normalize
        length = loss1[i] ** 2 + loss2[i] ** 2 + 1e-8
        diff = diff + (loss1[i] - loss2[i]) ** 2 / length**2
    print("[SOK INFO] loss diff:", diff)
    assert diff < 1e-4

    print("[SOK INFO] lookup_sparse localized test passed")
    ts = ts[5:]
    print("[SOK INFO] Average time: %f ms/iteration" % (sum(ts) / len(ts) * 1000))
