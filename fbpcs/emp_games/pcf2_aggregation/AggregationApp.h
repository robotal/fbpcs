/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#pragma once

#include <fbpcf/io/api/FileIOWrappers.h>
#include <fbpcf/scheduler/LazySchedulerFactory.h>
#include <fbpcf/scheduler/NetworkPlaintextSchedulerFactory.h>
#include "fbpcf/engine/communication/IPartyCommunicationAgentFactory.h"
#include "fbpcs/emp_games/common/SchedulerStatistics.h"
#include "fbpcs/emp_games/pcf2_aggregation/AggregationGame.h"
#include "fbpcs/emp_games/pcf2_aggregation/AggregationOptions.h"

namespace pcf2_aggregation {

template <int MY_ROLE, int schedulerId>
class AggregationApp {
 public:
  AggregationApp(
      common::InputEncryption inputEncryption,
      common::Visibility outputVisibility,
      std::unique_ptr<
          fbpcf::engine::communication::IPartyCommunicationAgentFactory>
          communicationAgentFactory,
      const std::string& aggregationFormat,
      const std::vector<std::string>& inputSecretShareFilePaths,
      const std::vector<std::string>& inputClearTextFilePaths,
      const std::vector<std::string>& outputFilePaths,
      std::int32_t startFileIndex = 0,
      std::int32_t numFiles = 1,
      int concurrency = 1)
      : inputEncryption_(inputEncryption),
        outputVisibility_(outputVisibility),
        communicationAgentFactory_(std::move(communicationAgentFactory)),
        aggregationFormat_{aggregationFormat},
        inputSecretShareFilePaths_(inputSecretShareFilePaths),
        inputClearTextFilePaths_(inputClearTextFilePaths),
        outputFilePaths_(outputFilePaths),
        startFileIndex_(startFileIndex),
        numFiles_(numFiles),
        concurrency_(concurrency),
        schedulerStatistics_{0, 0, 0, 0} {}

  void run() {
    auto scheduler = outputVisibility_ == common::Visibility::Publisher
        ? fbpcf::scheduler::NetworkPlaintextSchedulerFactory<false>(
              MY_ROLE, *communicationAgentFactory_)
              .create()
        : fbpcf::scheduler::getLazySchedulerFactoryWithRealEngine(
              MY_ROLE, *communicationAgentFactory_)
              ->create();
    auto metricsCollector = communicationAgentFactory_->getMetricsCollector();

    AggregationGame<schedulerId> game(
        std::move(scheduler),
        std::move(communicationAgentFactory_),
        inputEncryption_,
        concurrency_);

    // Compute aggregations sequentially on numFiles files, starting from
    // startFileIndex
    for (size_t i = startFileIndex_; i < startFileIndex_ + numFiles_; ++i) {
      CHECK_LT(i, inputSecretShareFilePaths_.size())
          << "File index exceeds number of files.";
      auto inputData = getInputData(
          inputEncryption_,
          inputSecretShareFilePaths_.at(i),
          inputClearTextFilePaths_.at(i));
      AggregationOutputMetrics output;
      if (FLAGS_use_new_output_format) {
        output = game.computeAggregationsReformatted(MY_ROLE, inputData);
      } else {
        output = game.computeAggregations(MY_ROLE, inputData);
      }
      putOutputData(output, outputFilePaths_.at(i));
    }

    auto gateStatistics =
        fbpcf::scheduler::SchedulerKeeper<schedulerId>::getGateStatistics();
    XLOGF(
        INFO,
        "Non-free gate count = {}, Free gate count = {}",
        gateStatistics.first,
        gateStatistics.second);

    auto trafficStatistics =
        fbpcf::scheduler::SchedulerKeeper<schedulerId>::getTrafficStatistics();
    XLOGF(
        INFO,
        "Sent network traffic = {}, Received network traffic = {}",
        trafficStatistics.first,
        trafficStatistics.second);

    schedulerStatistics_.nonFreeGates = gateStatistics.first;
    schedulerStatistics_.freeGates = gateStatistics.second;
    schedulerStatistics_.sentNetwork = trafficStatistics.first;
    schedulerStatistics_.receivedNetwork = trafficStatistics.second;
    schedulerStatistics_.details = metricsCollector->collectMetrics();
  }

  common::SchedulerStatistics getSchedulerStatistics() {
    return schedulerStatistics_;
  }

 protected:
  AggregationInputMetrics getInputData(
      common::InputEncryption inputEncryption,
      std::string inputSecretShareFilePath,
      std::string inputClearTextFilePath) {
    XLOG(INFO) << "MY_ROLE: " << MY_ROLE << ", schedulerId: " << schedulerId
               << ", aggregationFormat_: " << aggregationFormat_
               << ", input_secret_share_file_path: " << inputSecretShareFilePath
               << ", input_clear_text_file_path: " << inputClearTextFilePath;
    return AggregationInputMetrics{
        MY_ROLE,
        inputEncryption,
        inputSecretShareFilePath,
        inputClearTextFilePath,
        aggregationFormat_,
    };
  }

  void putOutputData(
      const AggregationOutputMetrics& aggregationOutput,
      std::string outputPath) {
    fbpcf::io::FileIOWrappers::writeFile(
        outputPath, aggregationOutput.toJson());
  }

 private:
  common::InputEncryption inputEncryption_;
  common::Visibility outputVisibility_;
  std::unique_ptr<fbpcf::engine::communication::IPartyCommunicationAgentFactory>
      communicationAgentFactory_;
  std::string serverIp_;
  uint16_t port_;
  std::string aggregationFormat_;
  std::vector<std::string> inputSecretShareFilePaths_;
  std::vector<std::string> inputClearTextFilePaths_;
  std::vector<std::string> outputFilePaths_;
  const std::int32_t startFileIndex_;
  const std::int32_t numFiles_;
  const int concurrency_;
  common::SchedulerStatistics schedulerStatistics_;
};

} // namespace pcf2_aggregation
