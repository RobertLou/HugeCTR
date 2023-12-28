"""
 Copyright (c) 2023, NVIDIA CORPORATION.
 
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

import hugectr
from mpi4py import MPI

# 1. Create Solver, DataReaderParams and Optimizer
solver = hugectr.CreateSolver(
    max_eval_batches=50,
    batchsize_eval=1792000,
    batchsize=71680,
    vvgpu=[
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [0, 1, 2, 3, 4, 5, 6, 7],
    ],
    repeat_dataset=True,
    lr=26.0,
    warmup_steps=2500,
    decay_start=46821,
    decay_steps=15406,
    decay_power=2.0,
    end_lr=0.0,
    use_mixed_precision=True,
    scaler=1024,
    use_cuda_graph=True,
    gen_loss_summary=False,
    train_intra_iteration_overlap=True,
    train_inter_iteration_overlap=True,
    eval_intra_iteration_overlap=True,
    eval_inter_iteration_overlap=True,
    all_reduce_algo=hugectr.AllReduceAlgo.OneShot,
    grouped_all_reduce=True,
    num_iterations_statistics=20,
    metrics_spec={hugectr.MetricsType.AUC: 0.8025},
    perf_logging=True,
    drop_incomplete_batch=False,
)

batchsize = 71680
num_reading_threads = 32
num_batches_per_threads = 4
expected_io_block_size = batchsize * 10
io_depth = 2
io_alignment = 512
bytes_size_per_batches = (26 + 1 + 13) * 4 * batchsize
max_nr_per_threads = num_batches_per_threads * (
    bytes_size_per_batches // expected_io_block_size + 2
)

reader = hugectr.DataReaderParams(
    data_reader_type=hugectr.DataReaderType_t.RawAsync,
    source=["/raid/datasets/criteo/mlperf/40m.limit_preshuffled/train_data.bin"],
    eval_source="/raid/datasets/criteo/mlperf/40m.limit_preshuffled/test_data.bin",
    check_type=hugectr.Check_t.Non,
    num_samples=4195197692,
    eval_num_samples=89137319,
    cache_eval_data=50,
    slot_size_array=[
        39884406,
        39043,
        17289,
        7420,
        20263,
        3,
        7120,
        1543,
        63,
        38532951,
        2953546,
        403346,
        10,
        2208,
        11938,
        155,
        4,
        976,
        14,
        39979771,
        25641295,
        39664984,
        585935,
        12972,
        108,
        36,
    ],
    async_param=hugectr.AsyncParam(
        num_reading_threads,
        num_batches_per_threads,
        max_nr_per_threads,
        io_depth,
        io_alignment,
        True,
        hugectr.Alignment_t.Auto,
        multi_hot_reader=False,
        is_dense_float=False,
    ),
)
optimizer = hugectr.CreateOptimizer(
    optimizer_type=hugectr.Optimizer_t.SGD, update_type=hugectr.Update_t.Local, atomic_update=True
)
# 2. Initialize the Model instance
model = hugectr.Model(solver, reader, optimizer)
# 3. Construct the Model graph
model.add(
    hugectr.Input(
        label_dim=1,
        label_name="label",
        dense_dim=13,
        dense_name="dense",
        data_reader_sparse_param_array=[hugectr.DataReaderSparseParam("data1", 1, True, 26)],
    )
)

# Use mean num of infrequent plus 10-sigma guardband
model.add(
    hugectr.SparseEmbedding(
        embedding_type=hugectr.Embedding_t.HybridSparseEmbedding,
        workspace_size_per_gpu_in_mb=1500,
        slot_size_array=[
            39884406,
            39043,
            17289,
            7420,
            20263,
            3,
            7120,
            1543,
            63,
            38532951,
            2953546,
            403346,
            10,
            2208,
            11938,
            155,
            4,
            976,
            14,
            39979771,
            25641295,
            39664984,
            585935,
            12972,
            108,
            36,
        ],
        embedding_vec_size=128,
        combiner="sum",
        sparse_embedding_name="sparse_embedding1",
        bottom_name="data1",
        optimizer=optimizer,
        hybrid_embedding_param=hugectr.HybridEmbeddingParam(
            2,
            16640 + 1290,
            0.01,
            1.3e11,
            23.75e9,
            0.5,
            hugectr.CommunicationType.IB_NVLink_Hier,
            hugectr.HybridEmbeddingType.Distributed,
        ),
    )
)
compute_config_bottom = hugectr.DenseLayerComputeConfig(
    async_wgrad=True,
    fuse_wb=False,
)

compute_config_top = hugectr.DenseLayerComputeConfig(
    async_wgrad=True,
    fuse_wb=True,
)
model.add(
    hugectr.DenseLayer(
        layer_type=hugectr.Layer_t.MLP,
        bottom_names=["dense"],
        top_names=["mlp1"],
        num_outputs=[512, 256, 128],
        compute_config=compute_config_bottom,
        act_type=hugectr.Activation_t.Relu,
        use_bias=True,
    )
)

model.add(
    hugectr.DenseLayer(
        layer_type=hugectr.Layer_t.Interaction,
        bottom_names=["mlp1", "sparse_embedding1"],
        top_names=["interaction1", "interaction_grad"],
    )
)
model.add(
    hugectr.DenseLayer(
        layer_type=hugectr.Layer_t.MLP,
        bottom_names=["interaction1", "interaction_grad"],
        top_names=["mlp2"],
        num_outputs=[1024, 1024, 512, 256, 1],
        compute_config=compute_config_top,
        use_bias=True,
        activations=[
            hugectr.Activation_t.Relu,
            hugectr.Activation_t.Relu,
            hugectr.Activation_t.Relu,
            hugectr.Activation_t.Relu,
            hugectr.Activation_t.Non,
        ],
    )
)
model.add(
    hugectr.DenseLayer(
        layer_type=hugectr.Layer_t.BinaryCrossEntropyLoss,
        bottom_names=["mlp2", "label"],
        top_names=["loss"],
    )
)
# 4. Dump the Model graph to JSON
model.graph_to_json(graph_config_file="dlrm.json")
# 5. Compile & Fit
model.compile()
model.summary()
model.fit(
    max_iter=58527, display=1000, eval_interval=2926, snapshot=2000000, snapshot_prefix="dlrm"
)
