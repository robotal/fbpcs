/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <fbpcf/io/api/FileIOWrappers.h>
#include <filesystem>
#include <string>

#include <gtest/gtest.h>
#include "folly/Format.h"
#include "folly/Random.h"
#include "folly/logging/xlog.h"

#include "fbpcf/engine/communication/SocketPartyCommunicationAgentFactory.h"
#include "fbpcf/engine/communication/test/SocketInTestHelper.h"
#include "fbpcf/engine/communication/test/TlsCommunicationUtils.h"
#include "fbpcf/scheduler/SchedulerHelper.h"
#include "fbpcf/test/TestHelper.h"

#include "fbpcf/engine/communication/test/AgentFactoryCreationHelper.h"
#include "fbpcs/emp_games/common/TestUtil.h"
#include "fbpcs/emp_games/dotproduct/DotproductGame.h"

namespace pcf2_dotproduct {

template <int PARTY, int schedulerId>
std::vector<bool> runORLabelsGame(
    std::unique_ptr<
        fbpcf::engine::communication::IPartyCommunicationAgentFactory> factory,
    fbpcf::SchedulerCreator schedulerCreator,
    std::vector<std::vector<bool>> labels) {
  auto scheduler = schedulerCreator(PARTY, *factory);

  DotproductGame<schedulerId> game(std::move(scheduler), std::move(factory));

  // Create label secret shares
  auto labelShare = game.createSecretLabelShare(labels);

  // Do ORing of all the labels
  auto finalLabel = game.orAllLabels(labelShare);

  // Extracting label values
  auto labelVec = finalLabel.extractBit().getValue();

  return labelVec;
}

std::vector<std::vector<bool>> getBooleanLabels(
    std::vector<std::string> labelStringVec,
    int labelWidth) {
  std::vector<std::vector<bool>> allLabels;
  for (int i = 0; i < labelWidth; i++) {
    std::vector<bool> labelRow(labelStringVec.size());

    for (int j = 0; j < labelStringVec.size(); j++) {
      labelRow[j] = (labelStringVec[j][i] == '1');
    }

    allLabels.push_back(labelRow);
  }
  return allLabels;
}

void testORLabels(fbpcf::SchedulerType schedulerType) {
  auto factories = fbpcf::engine::communication::getInMemoryAgentFactory(2);
  const bool unsafe = true;
  fbpcf::SchedulerCreator schedulerCreator =
      fbpcf::getSchedulerCreator<unsafe>(schedulerType);

  int LABEL_WIDTH = 16;

  // Each row is a stream of 16 labels (if the row is identical between
  // labels1 and labels2 then then the final label is zero)
  std::vector<std::string> labels1{
      "0000000000000000",
      "1111111111111111",
      "0000000000000000",
      "1000101010111011",
      "1000010011111101",
      "1110110000101011",
      "1100000001011100"};
  std::vector<std::string> labels2{
      "0000000000000000",
      "1111111111111111",
      "1111111111111111",
      "1000101010111011",
      "1000010011111101",
      "1010110000101011",
      "1100000001011111"};

  // expected result
  std::vector<bool> expectedResult = {
      false, false, true, false, false, true, true};

  // convert input labels to 2D boolean vector
  std::vector<std::vector<bool>> labelsAlice =
      getBooleanLabels(labels1, LABEL_WIDTH);

  std::vector<std::vector<bool>> labelsBob =
      getBooleanLabels(labels2, LABEL_WIDTH);

  // run the game for publisher and partner
  auto futureAlice = std::async(
      runORLabelsGame<0, 0>,
      std::move(factories[0]),
      schedulerCreator,
      labelsAlice);
  auto futureBob = std::async(
      runORLabelsGame<1, 1>,
      std::move(factories[1]),
      schedulerCreator,
      labelsBob);
  auto finalLabelAlice = futureAlice.get();
  auto finalLabelBob = futureBob.get();

  // Do Xor for the result shares
  std::vector<bool> result;
  for (size_t i = 0; i < finalLabelAlice.size(); i++) {
    auto plainTextLabel = finalLabelAlice.at(i) ^ finalLabelBob.at(i);
    result.push_back(plainTextLabel);
  }

  EXPECT_EQ(result, expectedResult);
}
/* run the same tests with multiple schedulers */
class DotproductGameTestFixture
    : public ::testing::TestWithParam<fbpcf::SchedulerType> {};

TEST_P(DotproductGameTestFixture, TestORAllLabels) {
  auto schedulerType = GetParam();
  testORLabels(schedulerType);
}

INSTANTIATE_TEST_SUITE_P(
    DotproductGameTest,
    DotproductGameTestFixture,
    ::testing::Values(
        fbpcf::SchedulerType::NetworkPlaintext,
        fbpcf::SchedulerType::Eager,
        fbpcf::SchedulerType::Lazy),
    [](const testing::TestParamInfo<DotproductGameTestFixture::ParamType>&
           info) {
      auto schedulerType = info.param;
      return fbpcf::getSchedulerName(schedulerType);
    });

} // namespace pcf2_dotproduct
