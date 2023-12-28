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


if __name__ == "__main__":
    dim = 128
    vocab_size = 1024 * 128
    batch = 8192

    optimizers = [
        tf.optimizers.SGD(learning_rate=1.0),
        tf.optimizers.SGD(learning_rate=1.0, momentum=0.9),
        tf.optimizers.Adamax(learning_rate=1.0, beta_1=0.9, beta_2=0.999),
        tf.optimizers.Adadelta(learning_rate=1.0),
        tf.optimizers.Adagrad(learning_rate=1.0),
        tf.optimizers.Ftrl(learning_rate=1.0),
        # tf.optimizers.RMSprop(learning_rate=1.0),
        # tf.optimizers.Adam(learning_rate=1.0, beta_1=0.9, beta_2=0.999),
        # tf.optimizers.Nadam(learning_rate=1.0),
    ]

    for optimizer_id, optimizer in enumerate(optimizers):
        sok_var = sok.DynamicVariable(dimension=dim)
        sok_optimizer = sok.OptimizerWrapper(optimizer)

        indices_val = [idx for idx in range(vocab_size)]
        table_val = tf.nn.embedding_lookup(sok_var, indices_val)
        tf_var = tf.Variable(table_val)
        tf_optimizer = optimizer

        def sok_step(indices, weight, var):
            with tf.GradientTape() as tape:
                emb = tf.nn.embedding_lookup(var, indices)
                emb_mul = emb * weight
                loss = tf.reduce_sum(emb_mul)
            grads = tape.gradient(loss, [var])
            sok_optimizer.apply_gradients(zip(grads, [var]))
            return loss

        @tf.function
        def tf_step(indices, weight, var):
            with tf.GradientTape() as tape:
                emb = tf.nn.embedding_lookup(var, indices)
                emb_mul = emb * weight
                loss = tf.reduce_sum(emb_mul)
            grads = tape.gradient(loss, [var])
            tf_optimizer.apply_gradients(zip(grads, [var]))
            return loss

        num = np.random.randint(1, batch + 1, 1)[0]
        for i in range(100):
            print("---------------------Iter %d---------------------" % i)
            indices_val = np.random.randint(0, vocab_size, num).astype(np.int64)
            indices_val = tf.convert_to_tensor(indices_val, dtype=tf.int64)
            weight_val = np.random.rand(num, dim).astype(np.float32)
            weight_val = tf.convert_to_tensor(weight_val, dtype=tf.float32)
            sok_loss = sok_step(indices_val, weight_val, sok_var)
            tf_loss = tf_step(indices_val, weight_val, tf_var)
            print(sok_loss, tf_loss)

        indices_val = [idx for idx in range(vocab_size)]
        table_val = tf.nn.embedding_lookup(sok_var, indices_val)
        diff = tf.reduce_mean((table_val - tf_var) ** 2.0)
        if diff >= 1e-6:
            print(optimizer)
        assert diff < 1e-6
        print("[SOK INFO] %dth test variable successfully" % optimizer_id)

        # ----------------------------Test eager mode----------------------------

        def sok_step_eager(indices, weight, var):
            with tf.GradientTape() as tape:
                emb = tf.nn.embedding_lookup(var, indices)
                emb_mul = emb * weight
                loss = tf.reduce_sum(emb_mul)
            grads = tape.gradient(loss, [var])
            sok_optimizer.apply_gradients(zip(grads, [var]))
            return loss

        def tf_step_eager(indices, weight, var):
            with tf.GradientTape() as tape:
                emb = tf.nn.embedding_lookup(var, indices)
                emb_mul = emb * weight
                loss = tf.reduce_sum(emb_mul)
            grads = tape.gradient(loss, [var])
            tf_optimizer.apply_gradients(zip(grads, [var]))
            return loss

        for i in range(100):
            num = np.random.randint(1, batch + 1, 1)[0]
            print("---------------------Iter %d---------------------" % i)
            indices_val = np.random.randint(0, vocab_size, num).astype(np.int64)
            indices_val = tf.convert_to_tensor(indices_val, dtype=tf.int64)
            weight_val = np.random.rand(num, dim).astype(np.float32)
            weight_val = tf.convert_to_tensor(weight_val, dtype=tf.float32)
            sok_loss = sok_step_eager(indices_val, weight_val, sok_var)
            tf_loss = tf_step_eager(indices_val, weight_val, tf_var)
            print(sok_loss, tf_loss)

        indices_val = [idx for idx in range(vocab_size)]
        table_val = tf.nn.embedding_lookup(sok_var, indices_val)
        diff = tf.reduce_mean((table_val - tf_var) ** 2.0)
        if diff >= 1e-6:
            print(optimizer)
        assert diff < 1e-6
        print("[SOK INFO] %dth test variable eager successfully" % optimizer_id)
