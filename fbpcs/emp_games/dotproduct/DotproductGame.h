/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#pragma once

#include "folly/logging/xlog.h"

#include "fbpcf/frontend/mpcGame.h"
#include "fbpcs/emp_games/common/Debug.h"
#include "fbpcs/emp_games/common/Util.h"
#include "fbpcs/emp_games/dotproduct/DotproductOptions.h"

namespace pcf2_dotproduct {

template <int schedulerId>
class DotproductGame : public fbpcf::frontend::MpcGame<schedulerId> {
 public:
  explicit DotproductGame(
      std::unique_ptr<fbpcf::scheduler::IScheduler> scheduler,
      std::shared_ptr<
          fbpcf::engine::communication::IPartyCommunicationAgentFactory>
          communicationAgentFactory)
      : fbpcf::frontend::MpcGame<schedulerId>(std::move(scheduler)),
        communicationAgentFactory_(communicationAgentFactory) {}

  std::vector<double> computeDotProduct(
      const int myRole,
      const std::tuple<
          std::vector<std::vector<double>>,
          std::vector<std::vector<bool>>> inputTuple,
      size_t nLabels,
      size_t nFeatures,
      const bool debugMode);

  std::shared_ptr<fbpcf::engine::communication::IPartyCommunicationAgentFactory>
      communicationAgentFactory_;

  std::vector<fbpcf::frontend::Bit<true, schedulerId, true>>
  createSecretLabelShare(const std::vector<std::vector<bool>>& labelValues);

  fbpcf::frontend::Bit<true, schedulerId, true> orAllLabels(
      const std::vector<fbpcf::frontend::Bit<true, schedulerId, true>>& labels);
};

} // namespace pcf2_dotproduct

#include "fbpcs/emp_games/dotproduct/DotproductGame_impl.h"
