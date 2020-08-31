/*
 * Copyright (c) 2020, NVIDIA CORPORATION.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "HugeCTR/include/layers/dropout_cudnn_layer.hpp"

#include <cublas_v2.h>
#include <gtest/gtest.h>
#include <utest/test_utils.h>
#include <cmath>
#include <cstdlib>
#include <utils.hpp>
#include <vector>

using namespace std;
using namespace HugeCTR;

namespace {

const float eps = 1e-6;

template <typename T>
void dropout_test(size_t dim0, size_t dim1, float rate) {
  std::shared_ptr<GeneralBuffer2<CudaAllocator>> buf = GeneralBuffer2<CudaAllocator>::create();
  vector<size_t> dims = {dim0, dim1};
  Tensor2<T> in_tensor;
  buf->reserve(dims, &in_tensor);
  Tensor2<T> out_tensor;
  buf->reserve(dims, &out_tensor);

  DropoutCudnnLayer<T> dropout_layer(in_tensor, out_tensor, buf, rate, test::get_default_gpu());

  buf->allocate();

  const int len = dim0 * dim1;
  const int n_bytes = len * sizeof(T);
  T* d_in = in_tensor.get_ptr();
  //  T* d_out = out_tensor.get_ptr();

  std::unique_ptr<T[]> h_in(new T[len]);
  std::unique_ptr<T[]> h_out(new T[len]);
  test::GaussianDataSimulator simulator(0.0f, 1.0f);

  simulator.fill(h_in.get(), len);
  cudaMemcpy(d_in, h_in.get(), n_bytes, cudaMemcpyHostToDevice);

  std::unique_ptr<float[]> h_mask(new float[len]);
  std::unique_ptr<T[]> h_ref(new T[len]);

  // fprop test
  dropout_layer.fprop(true);

  // bprop test
  dropout_layer.bprop();
  cudaMemcpy(h_in.get(), d_in, n_bytes, cudaMemcpyDeviceToHost);
}

TEST(dropout_cudnn_layer, fp32_32x320_25) { dropout_test<float>(32, 320, 0.25); }

TEST(dropout_cudnn_layer, fp32_32x320_50) { dropout_test<float>(32, 320, 0.50); }

TEST(dropout_cudnn_layer, fp32_32x320_75) { dropout_test<float>(32, 320, 0.75); }

TEST(dropout_cudnn_layer, fp32_32x320_99) { dropout_test<float>(32, 320, 0.99); }

TEST(dropout_cudnn_layer, fp16_32x320_25) { dropout_test<__half>(32, 320, 0.25); }

TEST(dropout_cudnn_layer, fp16_32x320_50) { dropout_test<__half>(32, 320, 0.50); }

TEST(dropout_cudnn_layer, fp16_32x320_75) { dropout_test<__half>(32, 320, 0.75); }

TEST(dropout_cudnn_layer, fp16_32x320_99) { dropout_test<__half>(32, 320, 0.99); }

}  // end namespace
