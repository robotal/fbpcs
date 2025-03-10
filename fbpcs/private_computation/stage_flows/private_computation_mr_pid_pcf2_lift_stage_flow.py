#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging

from fbpcs.private_computation.entity.pid_mr_config import Protocol

from fbpcs.private_computation.entity.private_computation_status import (
    PrivateComputationInstanceStatus,
)
from fbpcs.private_computation.service.id_spine_combiner_stage_service import (
    IdSpineCombinerStageService,
)
from fbpcs.private_computation.service.pcf2_lift_stage_service import (
    PCF2LiftStageService,
)
from fbpcs.private_computation.service.pid_mr_stage_service import PIDMRStageService
from fbpcs.private_computation.service.private_computation_stage_service import (
    PrivateComputationStageService,
    PrivateComputationStageServiceArgs,
)
from fbpcs.private_computation.service.utils import DEFAULT_CONTAINER_TIMEOUT_IN_SEC
from fbpcs.private_computation.stage_flows.private_computation_base_stage_flow import (
    PrivateComputationBaseStageFlow,
    PrivateComputationStageFlowData,
)


class PrivateComputationMrPidPCF2LiftStageFlow(PrivateComputationBaseStageFlow):
    """
    - Private Lift Stage Flow with UNION_PID_MR_MULTIKEY -
    This enum lists all of the supported stage types and maps to their possible statuses.
    It also provides methods to get information about the next or previous stage.

    NOTE: The order in which the enum members appear is the order in which the stages are intended
    to run. The _order_ variable is used to ensure member order is consistent (class attribute, removed during class creation).
    An exception is raised at runtime if _order_ is inconsistent with the actual member order.
    """

    # Specifies the order of the stages. Don't change this unless you know what you are doing.
    # pyre-fixme[15]: `_order_` overrides attribute defined in `Enum` inconsistently.
    _order_ = "CREATED PC_PRE_VALIDATION UNION_PID_MR_MULTIKEY ID_SPINE_COMBINER RESHARD PCF2_LIFT AGGREGATE POST_PROCESSING_HANDLERS"
    # Regarding typing fixme above, Pyre appears to be wrong on this one. _order_ only appears in the EnumMeta metaclass __new__ method
    # and is not actually added as a variable on the enum class. I think this is why pyre gets confused.

    CREATED = PrivateComputationStageFlowData(
        initialized_status=PrivateComputationInstanceStatus.CREATION_INITIALIZED,
        started_status=PrivateComputationInstanceStatus.CREATION_STARTED,
        completed_status=PrivateComputationInstanceStatus.CREATED,
        failed_status=PrivateComputationInstanceStatus.CREATION_FAILED,
        is_joint_stage=False,
    )
    PC_PRE_VALIDATION = PrivateComputationStageFlowData(
        initialized_status=PrivateComputationInstanceStatus.PC_PRE_VALIDATION_INITIALIZED,
        started_status=PrivateComputationInstanceStatus.PC_PRE_VALIDATION_STARTED,
        completed_status=PrivateComputationInstanceStatus.PC_PRE_VALIDATION_COMPLETED,
        failed_status=PrivateComputationInstanceStatus.PC_PRE_VALIDATION_FAILED,
        is_joint_stage=False,
    )
    UNION_PID_MR_MULTIKEY = PrivateComputationStageFlowData(
        initialized_status=PrivateComputationInstanceStatus.PID_MR_INITIALIZED,
        started_status=PrivateComputationInstanceStatus.PID_MR_STARTED,
        completed_status=PrivateComputationInstanceStatus.PID_MR_COMPLETED,
        failed_status=PrivateComputationInstanceStatus.PID_MR_FAILED,
        is_joint_stage=False,
    )
    ID_SPINE_COMBINER = PrivateComputationStageFlowData(
        initialized_status=PrivateComputationInstanceStatus.ID_SPINE_COMBINER_INITIALIZED,
        started_status=PrivateComputationInstanceStatus.ID_SPINE_COMBINER_STARTED,
        completed_status=PrivateComputationInstanceStatus.ID_SPINE_COMBINER_COMPLETED,
        failed_status=PrivateComputationInstanceStatus.ID_SPINE_COMBINER_FAILED,
        is_joint_stage=False,
    )
    RESHARD = PrivateComputationStageFlowData(
        initialized_status=PrivateComputationInstanceStatus.RESHARD_INITIALIZED,
        started_status=PrivateComputationInstanceStatus.RESHARD_STARTED,
        completed_status=PrivateComputationInstanceStatus.RESHARD_COMPLETED,
        failed_status=PrivateComputationInstanceStatus.RESHARD_FAILED,
        is_joint_stage=False,
    )
    PCF2_LIFT = PrivateComputationStageFlowData(
        initialized_status=PrivateComputationInstanceStatus.PCF2_LIFT_INITIALIZED,
        started_status=PrivateComputationInstanceStatus.PCF2_LIFT_STARTED,
        completed_status=PrivateComputationInstanceStatus.PCF2_LIFT_COMPLETED,
        failed_status=PrivateComputationInstanceStatus.PCF2_LIFT_FAILED,
        is_joint_stage=True,
        timeout=DEFAULT_CONTAINER_TIMEOUT_IN_SEC,  # setting the timeout here to 12 hours, as lift stage can sometime take more time.
    )
    AGGREGATE = PrivateComputationStageFlowData(
        initialized_status=PrivateComputationInstanceStatus.AGGREGATION_INITIALIZED,
        started_status=PrivateComputationInstanceStatus.AGGREGATION_STARTED,
        completed_status=PrivateComputationInstanceStatus.AGGREGATION_COMPLETED,
        failed_status=PrivateComputationInstanceStatus.AGGREGATION_FAILED,
        is_joint_stage=True,
    )
    POST_PROCESSING_HANDLERS = PrivateComputationStageFlowData(
        initialized_status=PrivateComputationInstanceStatus.POST_PROCESSING_HANDLERS_INITIALIZED,
        started_status=PrivateComputationInstanceStatus.POST_PROCESSING_HANDLERS_STARTED,
        completed_status=PrivateComputationInstanceStatus.POST_PROCESSING_HANDLERS_COMPLETED,
        failed_status=PrivateComputationInstanceStatus.POST_PROCESSING_HANDLERS_FAILED,
        is_joint_stage=False,
    )

    def get_stage_service(
        self, args: PrivateComputationStageServiceArgs
    ) -> PrivateComputationStageService:
        """
        Maps PrivateComputationMrPidPCF2LiftStageFlow instances to StageService instances

        Arguments:
            args: Common arguments initialized in PrivateComputationService that are consumed by stage services

        Returns:
            An instantiated StageService object corresponding to the StageFlow enum member caller.

        Raises:
            NotImplementedError: The subclass doesn't implement a stage service for a given StageFlow enum member
        """
        logging.info("Start MR stage flow")
        if self is self.UNION_PID_MR_MULTIKEY:
            if args.workflow_svc is None:
                raise NotImplementedError("workflow_svc is None")

            return PIDMRStageService(args.workflow_svc)
        elif self is self.ID_SPINE_COMBINER:
            return IdSpineCombinerStageService(
                args.onedocker_svc,
                args.onedocker_binary_config_map,
                protocol_type=Protocol.MR_PID_PROTOCOL.value,
            )
        elif self is self.PCF2_LIFT:
            return PCF2LiftStageService(
                args.onedocker_binary_config_map,
                args.mpc_svc,
            )
        else:
            return self.get_default_stage_service(args)
