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
 * @file game_pad_event.h
 * @brief Defines game pad event APIs for game app.
 * @kit GameControllerKit
 * @library libohgame_controller.z.so
 * @syscap SystemCapability.Game.GameController
 * @since 21
 */

#ifndef GAME_PAD_EVENT_H
#define GAME_PAD_EVENT_H

#include <stdint.h>
#include "game_controller_type.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Defines an enum for the axis events sources.
 * @since 21
 */
typedef enum GamePad_AxisSourceType {
    /**
     * Indicates the axis event from directional pad.
     */
    DPAD = 0,

    /**
     * Indicates the axis event from left thumbstick.
     */
    LEFT_THUMBSTICK = 1,

    /**
     * Indicates the axis event from right thumbstick.
     */
    RIGHT_THUMBSTICK = 2,

    /**
     * Indicates the axis event from left trigger.
     */
    LEFT_TRIGGER = 3,

    /**
     * Indicates the axis event from right trigger..
     */
    RIGHT_TRIGGER = 4,
} GamePad_AxisSourceType;

/**
 * @brief Defines an enum for the button action types.
 * @since 21
 */
typedef enum GamePad_Button_ActionType {
    /**
     * Pressing of a key
     */
    DOWN = 0,

    /**
     * Release of a key
     */
    UP = 1,
} GamePad_Button_ActionType;

/**
 * @brief Defines a struct for the button event of a game pad.
 * @since 21
 */
typedef struct GamePad_ButtonEvent GamePad_ButtonEvent;

/**
 * @brief Defines a struct for the axis events of a game pad.
 * @since 21
 */
typedef struct GamePad_AxisEvent GamePad_AxisEvent;

/**
 * @brief Defines a struct for the pressed button of a game pad.
 * @since 21
 */
typedef struct GamePad_PressedButton GamePad_PressedButton;

/**
 * @brief Defines a callback used in the monitor for the game pad button event.
 * This function is called when a game pad button is pressed.
 * @param buttonEvent Pointer to the {@link GamePad_ButtonEvent} instance.
 * @since 21
 */
typedef void(* GamePad_ButtonInputMonitorCallback)(const struct GamePad_ButtonEvent* buttonEvent);

/**
 * @brief Defines a callback used in {@link OH_GamePad_AddAxisInputMonitor}.
 * This function is called when the game pad axis is operated.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * @since 21
 */
typedef void(* GamePad_AxisInputMonitorCallback)(const struct GamePad_AxisEvent* axisEvent);

/**
 * @brief Obtains the device ID from {@link GamePad_ButtonEvent}.
 * @param buttonEvent Pointer to the {@link GamePad_ButtonEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param deviceId Double pointer to the device ID.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of buttonEvent or deviceId is null.
 * Returns {@link GAME_CONTROLLER_NO_MEMORY} if there is no sufficient memory.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonEvent_GetDeviceId(const struct GamePad_ButtonEvent* buttonEvent,
                                                            char** deviceId);

/**
 * @brief Obtains the button action type from {@link GamePad_ButtonEvent}.
 * @param buttonEvent Pointer to the {@link GamePad_ButtonEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param actionType Pointer to the action type.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of buttonEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonEvent_GetButtonAction(const struct GamePad_ButtonEvent* buttonEvent,
                                                                GamePad_Button_ActionType* actionType);
/**
 * @brief Obtains the button code from {@link GamePad_ButtonEvent}.
 * @param buttonEvent Pointer to the {@link GamePad_ButtonEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param code Pointer to the button code.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of buttonEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonEvent_GetButtonCode(const struct GamePad_ButtonEvent* buttonEvent,
                                                              int32_t* code);
/**
 * @brief Obtains the button name from {@link GamePad_ButtonEvent}.
 * @param buttonEvent Pointer to the {@link GamePad_ButtonEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param codeName Double pointer to the button name.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of buttonEvent or codeName is null.
 * Returns {@link GAME_CONTROLLER_NO_MEMORY} if there is no sufficient memory.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonEvent_GetButtonCodeName(const struct GamePad_ButtonEvent* buttonEvent,
                                                                  char** codeName);

/**
 * @brief Obtains the number of pressed buttons from {@link GamePad_ButtonEvent}.
 * @param buttonEvent Pointer to the {@link GamePad_ButtonEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param count Pointer to the number of pressed buttons.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of buttonEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_PressedButtons_GetCount(const struct GamePad_ButtonEvent* buttonEvent,
                                                            int32_t* count);

/**
 * @brief Obtains the button with a specified index from {@link GamePad_ButtonEvent}.
 * @param buttonEvent Pointer to the {@link GamePad_ButtonEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param index Specified button index.
 * @param pressedButton Double pointer to the pressed button.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of buttonEvent is null,
 * or if the value of index is less than 0 or greater than or equal to the total number of buttons.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_PressedButtons_GetButtonInfo(const struct GamePad_ButtonEvent* buttonEvent,
                                                                 const int32_t index,
                                                                 GamePad_PressedButton** pressedButton);

/**
 * @brief Destroys a {@link GamePad_PressedButton} instance when it is no longer used.
 * @param pressedButton Double pointer to the {@link GamePad_PressedButton} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of pressedButton is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_DestroyPressedButton(GamePad_PressedButton** pressedButton);

/**
 * @brief Obtains the button code from {@link GamePad_PressedButton}.
 * @param pressedButton Pointer to the {@link GamePad_PressedButton} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param code Pointer to the button code.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of pressedButton is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_PressedButton_GetButtonCode(const struct GamePad_PressedButton* pressedButton,
                                                                int32_t* code);

/**
 * @brief Obtains the button name from {@link GamePad_PressedButton}.
 * @param pressedButton Pointer to the {@link GamePad_PressedButton} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param codeName Double pointer to the button name.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of pressedButton or codeName is null.
 * Returns {@link GAME_CONTROLLER_NO_MEMORY} if there is no sufficient memory.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_PressedButton_GetButtonCodeName(const struct GamePad_PressedButton* pressedButton,
                                                                    char** codeName);
/**
 * @brief Obtains the action time from {@link GamePad_ButtonEvent}.
 * @param buttonEvent Pointer to the {@link GamePad_ButtonEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param actionTime Pointer to the action time.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of buttonEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_ButtonEvent_GetActionTime(const struct GamePad_ButtonEvent* buttonEvent,
                                                              int64_t* actionTime);

/**
 * @brief Obtains the device ID from {@link GamePad_AxisEvent}.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param deviceId Double pointer to the device ID.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of axisEvent or deviceId is null.
 * Returns {@link GAME_CONTROLLER_NO_MEMORY} if there is no sufficient memory.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_AxisEvent_GetDeviceId(const struct GamePad_AxisEvent* axisEvent,
                                                          char** deviceId);

/**
 * @brief Obtains the axis type from {@link GamePad_AxisEvent}.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param axisSourceType Pointer to the {@link GamePad_AxisSourceType} instance.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of axisEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_AxisEvent_GetAxisSourceType(const struct GamePad_AxisEvent* axisEvent,
                                                                GamePad_AxisSourceType* axisSourceType);

/**
 * @brief Obtains the value of the X axis from {@link GamePad_AxisEvent}.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param axisValue Pointer to the axis value.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of axisEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_AxisEvent_GetXAxisValue(const struct GamePad_AxisEvent* axisEvent,
                                                            double* axisValue);
/**
 * @brief Obtains the value of the Y axis from {@link GamePad_AxisEvent}.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param axisValue Pointer to the axis value.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of axisEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_AxisEvent_GetYAxisValue(const struct GamePad_AxisEvent* axisEvent,
                                                            double* axisValue);

/**
 * @brief Obtains the value of the Z axis from {@link GamePad_AxisEvent}.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param axisValue Pointer to the axis value.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of axisEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_AxisEvent_GetZAxisValue(const struct GamePad_AxisEvent* axisEvent,
                                                            double* axisValue);

/**
 * @brief Obtains the value of the RZ axis from {@link GamePad_AxisEvent}.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param axisValue Pointer to the axis value.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of axisEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_AxisEvent_GetRZAxisValue(const struct GamePad_AxisEvent* axisEvent,
                                                             double* axisValue);

/**
 * @brief Obtains the value of the HatX axis from {@link GamePad_AxisEvent}.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param axisValue Pointer to the axis value.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of axisEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_AxisEvent_GetHatXAxisValue(const struct GamePad_AxisEvent* axisEvent,
                                                               double* axisValue);

/**
 * @brief Obtains the value of the HatY axis from {@link GamePad_AxisEvent}.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param axisValue Pointer to the axis value.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of axisEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_AxisEvent_GetHatYAxisValue(const struct GamePad_AxisEvent* axisEvent,
                                                               double* axisValue);

/**
 * @brief Obtains the value of the Brake axis from {@link GamePad_AxisEvent}.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param axisValue Pointer to the axis value.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of axisEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_AxisEvent_GetBrakeAxisValue(const struct GamePad_AxisEvent* axisEvent,
                                                                double* axisValue);

/**
 * @brief Obtains the value of the Gas axis from {@link GamePad_AxisEvent}.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param axisValue Pointer to the axis value.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of axisEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_AxisEvent_GetGasAxisValue(const struct GamePad_AxisEvent* axisEvent,
                                                              double* axisValue);
/**
 * @brief Obtains the action time from {@link GamePad_AxisEvent}.
 * @param axisEvent Pointer to the {@link GamePad_AxisEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param actionTime Pointer to the action time.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of axisEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GamePad_AxisEvent_GetActionTime(const struct GamePad_AxisEvent* axisEvent,
                                                            int64_t* actionTime);

#ifdef __cplusplus
}
#endif

#endif //GAME_PAD_EVENT_H
/** @} */
