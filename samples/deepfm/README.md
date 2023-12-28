# CRITEO CTR SAMPLE #
The purpose of this sample is to demonstrate the basic usage of HugeCTR Python interface.

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
If you want to build the HugeCTR Docker container on your own, refer to [How to Start Your Development](https://nvidia-merlin.github.io/HugeCTR/master/hugectr_contributor_guide.html#how-to-start-your-development).

You should make sure that HugeCTR Python interface is built and installed in `/usr/local/hugectr` within the Docker container. You can launch the container in interactive mode in the same manner as shown above, and then set the `PYTHONPATH` environment variable inside the Docker container using the following command:
```shell
$ export PYTHONPATH=/usr/local/hugectr/lib:$PYTHONPATH
```

## Download the Dataset ##
Go [here](https://ailab.criteo.com/download-criteo-1tb-click-logs-dataset/) and download one of the dataset files into the "${project_root}/tools" directory. 

As an alternative, you can run the following command:
```
$ cd ${project_root}/tools
$ wget https://storage.googleapis.com/criteo-cail-datasets/day_1.gz
```

**NOTE**: Replace `1` with a value from [0, 23] to use a different day.

During preprocessing, the amount of data, which is used to speed up the preprocessing, fill missing values, and remove the feature values that are considered rare, is further reduced.

## Preprocess the Dataset ##
When running this sample, the [Criteo 1TB Click Logs dataset](https://ailab.criteo.com/download-criteo-1tb-click-logs-dataset/) is used. The dataset contains 24 files in which each file corresponds to one day of data. To reduce preprocessing time, only one file is used. Each sample consists of a label (0 if the ad wasn't clicked and 1 if the ad was clicked) and 39 features (13 integer features and 26 categorical features). The dataset is also missing numerous values across the feature columns, which should be preprocessed accordingly.

After you've downloaded the dataset, you can use [NVTabular](#preprocess-the-dataset-through-nvtabular) to prepare the dataset for HugeCTR training:

### Preprocess the Dataset Through NVTabular ###

HugeCTR supports data processing through NVTabular. Make sure that the NVTabular Docker environment has been set up successfully. For more information, see [NVTAbular github](https://github.com/NVIDIA/NVTabular). Ensure that you're using the latest version of NVTabular and mount the HugeCTR ${project_root} volume into the NVTabular Docker.

Execute the following preprocessing command:
   ```shell
$ bash preprocess.sh 1 criteo_data nvt 0 0
   ```

**IMPORTANT NOTES**: 

- The first argument represents the dataset postfix.  For example, if `day_1` is used, the postfix is `1`.
- The second argument `criteo_data` is where the preprocessed data is stored. You may want to change it in cases where multiple datasets are generated concurrently. If you change it, `source` and `eval_source` in your JSON configuration file must be changed as well.
- The fourth argument must be set to `1`. It means that criteo mode is ON, in another words, ignoring the dense features.
- The last argument determines whether the feature crossing should be applied (1=ON, 0=OFF). It must remain set to `0`.

## Train with HugeCTR ##

```shell
$ python3 ../samples/deepfm/deepfm_parquet.py
```

