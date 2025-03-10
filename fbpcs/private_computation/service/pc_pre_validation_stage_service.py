#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import logging
from typing import DefaultDict, List, Optional

from fbpcp.service.onedocker import OneDockerService
from fbpcs.common.entity.stage_state_instance import StageStateInstance
from fbpcs.common.service.trace_logging_service import (
    CheckpointStatus,
    TraceLoggingService,
)
from fbpcs.onedocker_binary_config import (
    ONEDOCKER_REPOSITORY_PATH,
    OneDockerBinaryConfig,
)
from fbpcs.onedocker_binary_names import OneDockerBinaryNames
from fbpcs.private_computation.entity.pc_validator_config import PCValidatorConfig
from fbpcs.private_computation.entity.private_computation_instance import (
    PrivateComputationInstance,
    PrivateComputationRole,
)
from fbpcs.private_computation.entity.private_computation_status import (
    PrivateComputationInstanceStatus,
)
from fbpcs.private_computation.service.pre_validation_util import get_cmd_args
from fbpcs.private_computation.service.private_computation_stage_service import (
    PrivateComputationStageService,
)
from fbpcs.private_computation.service.run_binary_base_service import (
    RunBinaryBaseService,
)
from fbpcs.private_computation.service.utils import get_pc_status_from_stage_state

# 20 minutes
PRE_VALIDATION_CHECKS_TIMEOUT: int = 1200


class PCPreValidationStageService(PrivateComputationStageService):
    """
    This PCPreValidation stage service validates input data files and
    binary files access.
    Validation fails if the issues detected in the data file
    do not pass the input_data_validation or if the binaries are not
    accessible. A failing validation stage will prevent the next
    stage from running.

    It is implemented in a Cloud agnostic way.
    """

    def __init__(
        self,
        pc_validator_config: PCValidatorConfig,
        onedocker_svc: OneDockerService,
        onedocker_binary_config_map: DefaultDict[str, OneDockerBinaryConfig],
        trace_logging_svc: Optional[TraceLoggingService] = None,
    ) -> None:
        self._logger: logging.Logger = logging.getLogger(__name__)
        self._failed_status: PrivateComputationInstanceStatus = (
            PrivateComputationInstanceStatus.PC_PRE_VALIDATION_FAILED
        )

        self._onedocker_binary_config_map = onedocker_binary_config_map
        self._pc_validator_config: PCValidatorConfig = pc_validator_config
        self._onedocker_svc = onedocker_svc
        self._trace_logging_svc = trace_logging_svc

    async def run_async(
        self,
        pc_instance: PrivateComputationInstance,
        server_ips: Optional[List[str]] = None,
    ) -> PrivateComputationInstance:
        """
        Updates the status to COMPLETED and returns the pc_instance
        """
        self._logger.info("[PCPreValidation] - Starting stage")
        if self._trace_logging_svc is not None:
            self._trace_logging_svc.write_checkpoint(
                run_id=pc_instance.infra_config.run_id,
                instance_id=pc_instance.infra_config.instance_id,
                checkpoint_name=pc_instance.current_stage.name,
                status=CheckpointStatus.STARTED,
            )

        if self._should_run_pre_validation(pc_instance):
            self._logger.info(
                "[PCPreValidation] - starting a pc_pre_validation_cli run"
            )
            await self.run_pc_pre_validation_cli(pc_instance)
        else:
            self._logger.info("[PCPreValidation] - skipped run validations")

        self._logger.info("[PCPreValidation] - finished run_async")
        return pc_instance

    async def run_pc_pre_validation_cli(
        self, pc_instance: PrivateComputationInstance
    ) -> None:
        region = self._pc_validator_config.region
        binary_name = OneDockerBinaryNames.PC_PRE_VALIDATION.value
        binary_config = self._onedocker_binary_config_map[binary_name]
        cmd_args = get_cmd_args(
            pc_instance.product_config.common.input_path,
            region,
            binary_config,
        )
        env_vars = {}
        if binary_config.repository_path:
            env_vars[ONEDOCKER_REPOSITORY_PATH] = binary_config.repository_path

        should_wait_spin_up: bool = (
            pc_instance.infra_config.role is PrivateComputationRole.PARTNER
        )
        container_instances = await RunBinaryBaseService().start_containers(
            cmd_args_list=[cmd_args],
            onedocker_svc=self._onedocker_svc,
            binary_version=binary_config.binary_version,
            binary_name=binary_name,
            timeout=PRE_VALIDATION_CHECKS_TIMEOUT,
            env_vars=env_vars,
            wait_for_containers_to_start_up=should_wait_spin_up,
        )

        stage_state = StageStateInstance(
            pc_instance.infra_config.instance_id,
            pc_instance.current_stage.name,
            containers=container_instances,
        )
        pc_instance.infra_config.instances.append(stage_state)
        self._logger.info(
            f"[PCPreValidation] - Started container instance_id: {container_instances[0].instance_id} status: {container_instances[0].status}"
        )

    def get_status(
        self,
        pc_instance: PrivateComputationInstance,
    ) -> PrivateComputationInstanceStatus:
        """
        Returns the pc_instance's current status
        """
        # When this stage is enabled, it should return the status based on the container status
        if self._should_run_pre_validation(pc_instance):
            instance_status = get_pc_status_from_stage_state(
                pc_instance, self._onedocker_svc
            )

            task_id = ""
            stage_instance = pc_instance.get_stage_instance()
            if stage_instance is not None:
                last_container = stage_instance.containers[-1]
                task_id = (
                    last_container.instance_id.split("/")[-1] if last_container else ""
                )

            if instance_status == self._failed_status and task_id:
                region = self._pc_validator_config.region
                cluster = self._onedocker_svc.get_cluster()
                failed_task_link = f"https://{region}.console.aws.amazon.com/ecs/home?region={region}#/clusters/{cluster}/tasks/{task_id}/details"

                error_message = (
                    f"[PCPreValidation] - stage failed because of some failed validations. Please check the logs in ECS for task id '{task_id}' to see the validation issues:\n"
                    + f"Failed task link: {failed_task_link}"
                )
                self._logger.error(error_message)
            elif instance_status == self._failed_status:
                self._logger.error(
                    "[PCPreValidation] - stage failed because of some failed validations. Please check the logs in ECS"
                )

            # adding to partner TL if needed
            return instance_status

        else:
            if self._trace_logging_svc is not None:
                self._trace_logging_svc.write_checkpoint(
                    run_id=pc_instance.infra_config.run_id,
                    instance_id=pc_instance.infra_config.instance_id,
                    checkpoint_name=pc_instance.current_stage.name,
                    status=CheckpointStatus.COMPLETED,
                )
            return PrivateComputationInstanceStatus.PC_PRE_VALIDATION_COMPLETED

    def _should_run_pre_validation(
        self, pc_instance: PrivateComputationInstance
    ) -> bool:
        return (
            self._pc_validator_config.pc_pre_validator_enabled
            and pc_instance.infra_config.role == PrivateComputationRole.PARTNER
        )
