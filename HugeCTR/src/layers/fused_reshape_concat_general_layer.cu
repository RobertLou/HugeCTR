/*
 * Copyright (c) 2023, NVIDIA CORPORATION.
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

#include <algorithm>
#include <functional>
#include <layers/fused_reshape_concat_general_layer.hpp>
#include <network_buffer_channels.hpp>
#include <utils.cuh>
#include <utils.hpp>

namespace HugeCTR {

namespace {

#define BLOCK_DIM_SIZE 32
template <typename T>
__global__ void fused_reshape_concat_general_kernel(bool forward, T** inputs, T* output,
                                                    int batch_size, int slot_num, size_t* vecs_size,
                                                    int output_width, int num) {
  int tid = blockIdx.x * blockDim.x + threadIdx.x;
  int threads_num = blockDim.x * gridDim.x;
  int out_size = batch_size * slot_num * output_width;

  for (int index = tid; index < out_size; index += threads_num) {
    int row = index / output_width;
    int out_col = index % output_width;

    int in_no = 0;
    int in_col = out_col;
    int accum_width = 0;
    for (int k = 0; k < num; k++) {
      if (out_col < accum_width + vecs_size[k]) {
        in_no = k;
        in_col -= accum_width;
        break;
      }
      accum_width += vecs_size[k];
    }
    T* in = inputs[in_no];
    int in_idx = row * vecs_size[in_no] + in_col;
    if (forward) {
      output[index] = in[in_idx];
    } else {
      in[in_idx] = output[index];
    }
  }
}

}  // end of namespace

template <typename T>
FusedReshapeConcatGeneralLayer<T>::FusedReshapeConcatGeneralLayer(
    const Tensors2<T>& in_tensors, Tensor2<T>& out_tensor,
    const std::shared_ptr<GeneralBuffer2<CudaAllocator>>& blobs_buff,
    const std::shared_ptr<GPUResource>& gpu_resource)
    : Layer(gpu_resource) {
  try {
    if (in_tensors.empty()) {
      HCTR_OWN_THROW(Error_t::WrongInput, "Empty input tensors");
    }

    num_ = in_tensors.size();
    for (size_t i = 0; i < num_; i++) {
      auto cur_in_dims = in_tensors[i].get_dimensions();
      if (i != 0) {
        auto first_in_dims = in_tensors[0].get_dimensions();
        if (cur_in_dims[0] != first_in_dims[0]) {
          HCTR_OWN_THROW(Error_t::WrongInput,
                         "All the input tensors must have the same batch_size");
        }
        if (cur_in_dims[1] != first_in_dims[1]) {
          HCTR_OWN_THROW(Error_t::WrongInput, "All the input tensors must have the same slot_num");
        }
      }
      if (cur_in_dims.size() != 3) {
        HCTR_OWN_THROW(Error_t::WrongInput, "All the input tensors must be 3D");
      }
      if (i == 0) {
        batch_size_ = cur_in_dims[0];
        slot_num_ = cur_in_dims[1];
      }
      new_width_ += cur_in_dims[2];
      h_vecs_size_.push_back(cur_in_dims[2]);
    }

    std::vector<size_t> out_dims = {batch_size_ * slot_num_, new_width_};
    blobs_buff->reserve(out_dims, &out_tensor);

    for (const Tensor2<T>& in_tensor : in_tensors) {
      in_tensors_.push_back(in_tensor);
    }
    out_tensor_ = out_tensor;
    blobs_buff->reserve({num_}, &d_inputs_);
    blobs_buff->reserve({num_}, &vecs_size_);

  } catch (const std::runtime_error& rt_err) {
    HCTR_LOG_S(ERROR, WORLD) << rt_err.what() << std::endl;
    throw;
  }
}

template <typename T>
void FusedReshapeConcatGeneralLayer<T>::initialize() {
  std::shared_ptr<GeneralBuffer2<CudaHostAllocator>> pinned_host_buf =
      GeneralBuffer2<CudaHostAllocator>::create();
  pinned_host_buf->reserve({num_}, &h_inputs_);
  pinned_host_buf->allocate();

  for (size_t i = 0; i < num_; i++) {
    h_inputs_.get_ptr()[i] = in_tensors_[i].get_ptr();
  }
  HCTR_LIB_THROW(cudaMemcpyAsync((void*)vecs_size_.get_ptr(), (void*)h_vecs_size_.data(),
                                 num_ * sizeof(size_t), cudaMemcpyHostToDevice,
                                 get_gpu().get_stream()));

  HCTR_LIB_THROW(cudaMemcpyAsync((void*)d_inputs_.get_ptr(), (void*)h_inputs_.get_ptr(),
                                 num_ * sizeof(T*), cudaMemcpyHostToDevice,
                                 get_gpu().get_stream()));
}

template <typename T>
void FusedReshapeConcatGeneralLayer<T>::fprop(bool is_train) {
  CudaDeviceContext context(get_device_id());
  Tensor2<T>& out_tensor = out_tensor_;
  T* output = out_tensor.get_ptr();
  dim3 block_size(256, 1, 1);
  size_t n_sms = get_gpu().get_sm_count();
  dim3 grid_size(n_sms * 8, 1, 1);
  fused_reshape_concat_general_kernel<<<grid_size, block_size, 0, get_gpu().get_stream()>>>(
      true, d_inputs_.get_ptr(), output, batch_size_, slot_num_, vecs_size_.get_ptr(), new_width_,
      num_);
}

template <typename T>
void FusedReshapeConcatGeneralLayer<T>::bprop() {
  CudaDeviceContext context(get_device_id());
  Tensor2<T>& out_tensor = out_tensor_;
  T* output = out_tensor.get_ptr();
  dim3 block_size(256, 1, 1);
  size_t n_sms = get_gpu().get_sm_count();
  dim3 grid_size(n_sms * 8, 1, 1);
  fused_reshape_concat_general_kernel<<<grid_size, block_size, 0, get_gpu().get_stream()>>>(
      false, d_inputs_.get_ptr(), output, batch_size_, slot_num_, vecs_size_.get_ptr(), new_width_,
      num_);
}
namespace core23 {

template <typename T>
FusedReshapeConcatGeneralLayer<T>::FusedReshapeConcatGeneralLayer(
    const std::vector<core23::Tensor>& in_tensors, core23::Tensor& out_tensor,
    const std::shared_ptr<GPUResource>& gpu_resource)
    : Layer(gpu_resource) {
  try {
    if (in_tensors.empty()) {
      HCTR_OWN_THROW(Error_t::WrongInput, "Empty input tensors");
    }
    core23::BufferParams blobs_buffer_params = {};
    blobs_buffer_params.channel = GetBlobsBufferChannel();
    num_ = in_tensors.size();
    for (int64_t i = 0; i < num_; i++) {
      auto cur_in_dims = in_tensors[i].shape();
      if (i != 0) {
        auto first_in_dims = in_tensors[0].shape();
        if (cur_in_dims[0] != first_in_dims[0]) {
          HCTR_OWN_THROW(Error_t::WrongInput,
                         "All the input tensors must have the same batch_size");
        }
        if (cur_in_dims[1] != first_in_dims[1]) {
          HCTR_OWN_THROW(Error_t::WrongInput, "All the input tensors must have the same slot_num");
        }
      }
      if (cur_in_dims.dims() != 3) {
        HCTR_OWN_THROW(Error_t::WrongInput, "All the input tensors must be 3D");
      }
      if (i == 0) {
        batch_size_ = cur_in_dims[0];
        slot_num_ = cur_in_dims[1];
      }
      new_width_ += cur_in_dims[2];
      h_vecs_size_.push_back(static_cast<uint64_t>(cur_in_dims[2]));
    }

    core23::Shape out_dims{batch_size_ * slot_num_, new_width_};
    out_tensor = core23::Tensor(in_tensors[0]
                                    .my_params()
                                    .data_type(core23::ToScalarType<T>::value)
                                    .shape(out_dims)
                                    .buffer_params(blobs_buffer_params));
    for (const core23::Tensor& in_tensor : in_tensors) {
      in_tensors_.push_back(in_tensor);
    }
    out_tensor_ = out_tensor;
    d_inputs_ = core23::Tensor(in_tensors[0]
                                   .my_params()
                                   .data_type(core23::ToScalarType<void*>::value)
                                   .shape({num_})
                                   .buffer_params(blobs_buffer_params));
    vecs_size_ = core23::Tensor(in_tensors[0]
                                    .my_params()
                                    .data_type(core23::ToScalarType<uint64_t>::value)
                                    .shape({num_})
                                    .buffer_params(blobs_buffer_params));
  } catch (const std::runtime_error& rt_err) {
    HCTR_LOG_S(ERROR, WORLD) << rt_err.what() << std::endl;
    throw;
  }
}

template <typename T>
void FusedReshapeConcatGeneralLayer<T>::initialize() {
  h_inputs_ = core23::Tensor(core23::TensorParams()
                                 .data_type(core23::ToScalarType<void*>::value)
                                 .shape({num_})
                                 .device(core23::Device(core23::DeviceType::CPU)));

  for (int64_t i = 0; i < num_; i++) {
    // data address
    uint64_t* to_write = h_inputs_.data<uint64_t>() + i;
    *to_write = reinterpret_cast<uint64_t>(in_tensors_[i].data());
  }
  HCTR_LIB_THROW(cudaMemcpyAsync((void*)vecs_size_.data(), (void*)h_vecs_size_.data(),
                                 num_ * sizeof(int64_t), cudaMemcpyHostToDevice,
                                 get_gpu().get_stream()));

  HCTR_LIB_THROW(cudaMemcpyAsync((void*)d_inputs_.data(), (void*)h_inputs_.data(),
                                 num_ * sizeof(T*), cudaMemcpyHostToDevice,
                                 get_gpu().get_stream()));
}

template <typename T>
void FusedReshapeConcatGeneralLayer<T>::fprop(bool is_train) {
  CudaDeviceContext context(get_device_id());
  core23::Tensor& out_tensor = out_tensor_;
  T* output = out_tensor.data<T>();
  dim3 block_size(256, 1, 1);
  size_t n_sms = get_gpu().get_sm_count();
  dim3 grid_size(n_sms * 8, 1, 1);
  fused_reshape_concat_general_kernel<<<grid_size, block_size, 0, get_gpu().get_stream()>>>(
      true, d_inputs_.data<T*>(), output, batch_size_, slot_num_, vecs_size_.data<size_t>(),
      new_width_, num_);
}

template <typename T>
void FusedReshapeConcatGeneralLayer<T>::bprop() {
  CudaDeviceContext context(get_device_id());
  core23::Tensor& out_tensor = out_tensor_;
  T* output = out_tensor.data<T>();
  dim3 block_size(256, 1, 1);
  size_t n_sms = get_gpu().get_sm_count();
  dim3 grid_size(n_sms * 8, 1, 1);
  fused_reshape_concat_general_kernel<<<grid_size, block_size, 0, get_gpu().get_stream()>>>(
      false, d_inputs_.data<T*>(), output, batch_size_, slot_num_, vecs_size_.data<size_t>(),
      new_width_, num_);
}
};  // namespace core23
template class FusedReshapeConcatGeneralLayer<float>;
template class core23::FusedReshapeConcatGeneralLayer<float>;

}  // namespace HugeCTR
