/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
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

/**
 * @addtogroup GameController
 * @{
 *
 * @brief Provides APIs for game controller capability.
 *
 * @since 21
 */

/**
 * @file game_pad.h
 * @brief Defines game pad capabilities APIs for game app.
 * @kit GameControllerKit
 * @library libohgame_controller.z.so
 * @syscap SystemCapability.Game.GameController
 * @since 21
 */

#ifndef GAME_PAD_H
#define GAME_PAD_H

#include <stdint.h>
#include "game_pad_event.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Registers a monitor for the left shoulder.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_LeftShoulder_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the left shoulder.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_LeftShoulder_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the right shoulder.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_RightShoulder_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the right shoulder.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_RightShoulder_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the left trigger.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_LeftTrigger_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the left trigger.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_LeftTrigger_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the axis events of the left trigger.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_AxisInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_LeftTrigger_RegisterAxisInputMonitor(
    GamePad_AxisInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the axis events of the left trigger.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_LeftTrigger_UnregisterAxisInputMonitor(void);

/**
 * @brief Registers a monitor for the right trigger.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 *  * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_RightTrigger_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the right trigger.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_RightTrigger_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the axis events of the right trigger.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_AxisInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_RightTrigger_RegisterAxisInputMonitor(
    GamePad_AxisInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the axis events of the right trigger.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_RightTrigger_UnregisterAxisInputMonitor(void);

/**
 * @brief Registers a monitor for the menu button.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonMenu_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the menu button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonMenu_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the Home button.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonHome_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the Home button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonHome_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the A button.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonA_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the A button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonA_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the B button.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonB_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the B button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonB_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the X button.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonX_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the X button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonX_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the Y button.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonY_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the Y button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonY_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the C button.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonC_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the C button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonC_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the left button.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_Dpad_LeftButton_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the left button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_Dpad_LeftButton_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the right button.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_Dpad_RightButton_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the right button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_Dpad_RightButton_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the up button.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_Dpad_UpButton_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the up button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_Dpad_UpButton_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the down button.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_Dpad_DownButton_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the down button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_Dpad_DownButton_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the axis events of directional buttons.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_AxisInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_Dpad_RegisterAxisInputMonitor(
    GamePad_AxisInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the axis events of directional buttons.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_Dpad_UnregisterAxisInputMonitor(void);

/**
 * @brief Registers a monitor for the button event of the left thumbstick.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_LeftThumbstick_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the button event of the left thumbstick.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_LeftThumbstick_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the axis events of the left thumbstick.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_AxisInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_LeftThumbstick_RegisterAxisInputMonitor(
    GamePad_AxisInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the axis events of the left thumbstick.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_LeftThumbstick_UnregisterAxisInputMonitor(void);

/**
 * @brief Registers a monitor for the button event of the right thumbstick.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_RightThumbstick_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the button event of the right thumbstick.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_RightThumbstick_UnregisterButtonInputMonitor(void);

/**
 * @brief Registers a monitor for the axis events of the right thumbstick.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_AxisInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_RightThumbstick_RegisterAxisInputMonitor(
    GamePad_AxisInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the axis events of the right thumbstick.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_RightThumbstick_UnregisterAxisInputMonitor(void);

/**
 * @brief Registers a monitor for the nonstandard button event.
 * @param inputMonitorCallback Callback function, which is {@link GamePad_ButtonInputMonitorCallback}.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of inputMonitorCallback is null.
 * @since 26.0.1
 */
GameController_ErrorCode OH_GamePad_ButtonNonstandard_RegisterButtonInputMonitor(
    GamePad_ButtonInputMonitorCallback inputMonitorCallback);

/**
 * @brief Unregisters the monitor for the nonstandard button event.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * @since 26.0.1
 */
GameController_ErrorCode OH_GamePad_ButtonNonstandard_UnregisterButtonInputMonitor(void);

#ifdef __cplusplus
}
#endif

#endif //GAME_PAD_H
/** @} */
