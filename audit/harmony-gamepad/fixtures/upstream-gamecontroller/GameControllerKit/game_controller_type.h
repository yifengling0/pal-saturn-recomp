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
 * @file game_controller_type.h
 * @brief Defines the common types for the native module.
 * @kit GameControllerKit
 * @library libohgame_controller.z.so
 * @syscap SystemCapability.Game.GameController
 * @since 21
 */

#ifndef GAME_CONTROLLER_TYPE_H
#define GAME_CONTROLLER_TYPE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif
/**
 * @brief Defines an enum for the error codes of GameController.
 * @since 21
 */
typedef enum GameController_ErrorCode {
    /**
     * Success.
     */
    GAME_CONTROLLER_SUCCESS = 0,

    /**
     * @error Invalid parameter.
     */
    GAME_CONTROLLER_PARAM_ERROR = 401,

    /**
     * @error The multimodal input is abnormal.
     */
    GAME_CONTROLLER_MULTIMODAL_INPUT_ERROR = 32200001,

    /**
     * @error There is no sufficient memory.
     */
    GAME_CONTROLLER_NO_MEMORY = 32200002,
} GameController_ErrorCode;

#ifdef __cplusplus
}
#endif

#endif //GAME_CONTROLLER_TYPE_H
/** @} */
