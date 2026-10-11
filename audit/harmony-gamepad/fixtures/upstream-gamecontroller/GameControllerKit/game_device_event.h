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
 * @file game_device_event.h
 * @brief Defines game device event APIs for game app.
 * @kit GameControllerKit
 * @library libohgame_controller.z.so
 * @syscap SystemCapability.Game.GameController
 * @since 21
 */

#ifndef GAME_DEVICE_EVENT_H
#define GAME_DEVICE_EVENT_H

#include <stdint.h>
#include "game_controller_type.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Defines an enum for the device status change types.
 * @since 21
 */
typedef enum GameDevice_StatusChangedType {
    /**
     * Indicates that the device is offline.
     */
    OFFLINE = 0,

    /**
     * Indicates that the device is online.
     */
    ONLINE = 1,
} GameDevice_StatusChangedType;

/**
 * @brief Defines an enum for the device types.
 * @since 21
 */
typedef enum GameDevice_DeviceType {
    /**
     * unknown
     */
    UNKNOWN = 0,

    /**
     * GamePad
     */
    GAME_PAD = 1,
} GameDevice_DeviceType;

/**
 * @brief Defines a struct for the device information.
 * @since 21
 */
typedef struct GameDevice_DeviceInfo GameDevice_DeviceInfo;

/**
 * @brief Defines a struct for the device event.
 * @since 21
 */
typedef struct GameDevice_DeviceEvent GameDevice_DeviceEvent;

/**
 * @brief Defines a callback used in {@link OH_GameDevice_RegisterDeviceMonitor}.
 * This function is called when a device goes online or offline.
 * @param deviceEvent Pointer to the {@link GameDevice_DeviceEvent} instance.
 * @since 21
 */
typedef void(* GameDevice_DeviceMonitorCallback)(const struct GameDevice_DeviceEvent* deviceEvent);

/**
 * @brief Obtains the device event change type.
 * @param deviceEvent Pointer to the {@link GameDevice_DeviceEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param statusChangedType Pointer to the device event change type.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} of the value of deviceEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GameDevice_DeviceEvent_GetChangedType(
    const struct GameDevice_DeviceEvent* deviceEvent,
    GameDevice_StatusChangedType* statusChangedType);

/**
 * @brief Obtains device information from a device event.
 * @param deviceEvent Pointer to the {@link GameDevice_DeviceEvent} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param deviceInfo Double pointer to the device information.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} of the value of deviceEvent is null.
 * @since 21
 */
GameController_ErrorCode OH_GameDevice_DeviceEvent_GetDeviceInfo(
    const struct GameDevice_DeviceEvent* deviceEvent,
    GameDevice_DeviceInfo** deviceInfo);

/**
 * @brief Destroys a {@link GameDevice_DeviceInfo} instance when it is no longer used.
 * @param deviceInfo Double pointer to the {@link GameDevice_DeviceInfo} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of deviceInfo is null.
 * @since 21
 */
GameController_ErrorCode OH_GameDevice_DestroyDeviceInfo(GameDevice_DeviceInfo** deviceInfo);

/**
 * @brief Obtains the device ID from {@link GameDevice_DeviceInfo}.
 * @param deviceInfo Pointer to the {@link GameDevice_DeviceInfo} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param deviceId Double pointer to the device ID.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of deviceInfo or deviceId is null.
 * Returns {@link GAME_CONTROLLER_NO_MEMORY} if there is no sufficient memory.
 * @since 21
 */
GameController_ErrorCode OH_GameDevice_DeviceInfo_GetDeviceId(const struct GameDevice_DeviceInfo* deviceInfo,
                                                              char** deviceId);
/**
 * @brief Obtains the device name from {@link GameDevice_DeviceInfo}.
 * @param deviceInfo Pointer to the {@link GameDevice_DeviceInfo} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param name Double pointer to the device name.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of deviceInfo or name is null.
 * Returns {@link GAME_CONTROLLER_NO_MEMORY} if there is no sufficient memory.
 * @since 21
 */
GameController_ErrorCode OH_GameDevice_DeviceInfo_GetName(const struct GameDevice_DeviceInfo* deviceInfo,
                                                          char** name);
/**
 * @brief Obtains product information from {@link GameDevice_DeviceInfo}.
 * @param deviceInfo Pointer to the {@link GameDevice_DeviceInfo} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param product Pointer to the product information.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of deviceInfo is null.
 * @since 21
 */
GameController_ErrorCode OH_GameDevice_DeviceInfo_GetProduct(const struct GameDevice_DeviceInfo* deviceInfo,
                                                             int32_t* product);

/**
 * @brief Obtains vendor information from {@link GameDevice_DeviceInfo}.
 * @param deviceInfo Pointer to the {@link GameDevice_DeviceInfo} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param vendor Pointer to the vendor information.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of deviceInfo is null.
 * @since 26.0.1
 */
GameController_ErrorCode OH_GameDevice_DeviceInfo_GetVendor(const struct GameDevice_DeviceInfo* deviceInfo,
                                                            int32_t* vendor);

/**
 * @brief Obtains the version information from {@link GameDevice_DeviceInfo}.
 * @param deviceInfo Pointer to the {@link GameDevice_DeviceInfo} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param version Pointer to the version information.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of deviceInfo is null.
 * @since 21
 */
GameController_ErrorCode OH_GameDevice_DeviceInfo_GetVersion(const struct GameDevice_DeviceInfo* deviceInfo,
                                                             int32_t* version);

/**
 * @brief Obtains the physical address from {@link GameDevice_DeviceInfo}.
 * @param deviceInfo Pointer to the {@link GameDevice_DeviceInfo} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param physicalAddress Double pointer to the physical address.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of deviceInfo or physicalAddress is null.
 * Returns {@link GAME_CONTROLLER_NO_MEMORY} if there is no sufficient memory.
 * @since 21
 */
GameController_ErrorCode OH_GameDevice_DeviceInfo_GetPhysicalAddress(const struct GameDevice_DeviceInfo* deviceInfo,
                                                                     char** physicalAddress);

/**
 * @brief Obtains the device type from {@link GameDevice_DeviceInfo}.
 * @param deviceInfo Pointer to the {@link GameDevice_DeviceInfo} instance.
 * The value cannot be null. Otherwise, an error code is returned.
 * @param deviceType Pointer to the device type.
 * @return Returns {@link GAME_CONTROLLER_SUCCESS} if the operation is successful.
 * Returns {@link GAME_CONTROLLER_PARAM_ERROR} if the value of deviceInfo is null.
 * @since 21
 */
GameController_ErrorCode OH_GameDevice_DeviceInfo_GetDeviceType(const struct GameDevice_DeviceInfo* deviceInfo,
                                                                GameDevice_DeviceType* deviceType);

#ifdef __cplusplus
}
#endif

#endif //GAME_DEVICE_EVENT_H
/** @} */
