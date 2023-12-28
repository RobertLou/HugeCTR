# DLRM CTR SAMPLE #

> **Deprecation Warning**: DLRM samples are based on the [one-hot RawAsync DataReader](https://nvidia-merlin.github.io/HugeCTR/main/api/python_interface.html#raw) and HybridEmbedding, both of which will be deprecated in a future release. Please check out the [multi-hot RawAsync DataReader]((https://nvidia-merlin.github.io/HugeCTR/main/api/python_interface.html#raw)) and [embedding collection](https://nvidia-merlin.github.io/HugeCTR/main/api/hugectr_layer_book.html#embedding-collection) for alternatives.

The purpose of this sample is to demonstrate how to build and train a [DLRM model](https://ai.facebook.com/blog/dlrm-an-advanced-open-source-deep-learning-recommendation-model/) with HugeCTR.

## Table of Contents
* [Set Up the HugeCTR Docker Environmen](#set-up-the-hugectr-docker-environment)
* [MLPerf DLRM](#mlperf-dlrm)
* [Kaggle DLRM](#kaggle-dlrm)

## Set Up the HugeCTR Docker Environment ##
You can set up the HugeCTR Docker environment by doing one of the following:
- [Pull the NGC Docker](#pull-the-ngc-docker)
- [Build the HugeCTR Docker Container on Your Own](#build-the-hugectr-docker-container-on-your-own)

### Pull the NGC Docker ###
HugeCTR is available as buildable source code, but the easiest way to install and run HugeCTR is to pull the pre-built Docker image, which is available on the NVIDIA GPU Cloud (NGC). This method provides a self-contained, isolated, and reproducible environment for repetitive experiments.

1. Pull the HugeCTR NGC Docker by running the following command:
   ```bash
   $ docker pull nvcr.io/nvidia/merlin/merlin-hugectr:23.12
   ```
2. Launch the container in interactive mode with the HugeCTR root directory mounted into the container by running the following command:
   ```bash
   $ docker run --gpus=all --rm -it --cap-add SYS_NICE -u $(id -u):$(id -g) -v $(pwd):/hugectr -w /hugectr nvcr.io/nvidia/merlin/merlin-hugectr:23.12
   ```

### Build the HugeCTR Docker Container on Your Own ###
Please refer to [How to Start Your Development](https://nvidia-merlin.github.io/HugeCTR/master/hugectr_contributor_guide.html#how-to-start-your-development) to build on your own and set up the Docker container. Make sure that HugeCTR is built and installed to the system path `/usr/local/hugectr` within the Docker container. Launch the container in interactive mode in the same manner as above, and then set the `PYTHONPATH` environment variable inside the Docker container using the following command:
```shell
$ export PYTHONPATH=/usr/local/hugectr/lib:$PYTHONPATH
```

## MLPerf DLRM
Ensure that you've met the following requirements:
- MLPerf v1.0: DGX A100 14 nodes

### Preprocess the Terabyte Click Logs ##
The [Terabyte Click Logs](https://labs.criteo.com/2013/12/download-terabyte-click-logs/) provided by CriteoLabs is used in this sample. The row count of each embedding table is limited to 40 million. The data is processed the same way as dlrm. For more information, see [Benchmarking](https://github.com/facebookresearch/dlrm#benchmarking). Each sample has 40 32-bit integers. The first integer is a label, the next 13 integers are dense features, and the last 26 integers are category features.

1. Download the terabyte datasets from the [Terabyte Click Logs](https://labs.criteo.com/2013/12/download-terabyte-click-logs/) into the `"${project_home}/samples/dlrm/"` folder.

2. Unzip the datasets and name them in the following manner: `day_0`, `day_1`, ..., `day_23`.

3. Preprocess the datasets using the following command:
   ```bash
   # Usage: dlrm_raw input_dir output_dir --train {days for training} --test {days for testing}
   $ dlrm_raw ./ ./ \
   --train 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22 \
   --test 23
   ```
   This operation will generate `train.bin(671.2GB)` and `test.bin(14.3GB)`.


### Run the Terabyte Click Logs with MLPerf v1.0 ##

Run the single node DGX-100 Python script using the following command:
   ```shell
   $ python3 dgx_a100.py
   ```

Run the 14-node DGX-100 Python script using the following command:
   ```shell
   $ numactl --interleave=all python3 dgx_a100_14x8x640.py
   ```

**IMPORTANT NOTES**: 
- To run the 14-node DGX-100 training script on Selene, you need to submit the job on the Selene login node properly.
- In v2.2.1, there is a CUDA Graph error that occurs when running this sample on DGX2. To run it on DGX2, specify `"use_cuda_graph = False` within `CreateSolver` in the Python script. For detailed information about this error, see [Known Issues](https://github.com/NVIDIA-Merlin/HugeCTR/blob/master/release_notes.md#known-issues).
- `cache_eval_data` is only supported on DGX A100. If you're running DGX2, disable it. 
