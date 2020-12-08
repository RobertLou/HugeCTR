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

#pragma once
#include <common.hpp>
#include <embedding.hpp>
#include <metrics.hpp>
#include <network.hpp>
#include <parser.hpp>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "HugeCTR/include/inference/hugectrmodel.hpp"

namespace HugeCTR {

class session_inference : public HugeCTRModel {
 public:
  session_inference(std::string model_name);
  virtual ~session_inference();
  void predict(float* dense, int* row, float* embeddingvector, float* output, int numofsamples);

 private:
  std::string model_name;
};

}  // namespace HugeCTR
