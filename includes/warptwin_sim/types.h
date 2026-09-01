/******************************************************************************
* Copyright (c) ATTX INC 2026. All Rights Reserved.
*
* This software and associated documentation (the "Software") are the 
* proprietary and confidential information of ATTX INC. The Software is 
* furnished under a license agreement between ATTX and the user organization 
* and may be used or copied only in accordance with the terms of the agreement.
* Refer to 'license/attx_license.adoc' for standard license terms.
*
* EXPORT CONTROL NOTICE: THIS SOFTWARE MAY INCLUDE CONTENT CONTROLLED UNDER THE
* INTERNATIONAL TRAFFIC IN ARMS REGULATIONS (ITAR) OR THE EXPORT ADMINISTRATION 
* REGULATIONS (EAR99). No part of the Software may be used, reproduced, or 
* transmitted in any form or by any means, for any purpose, without the express 
* written permission of ATTX INC.
******************************************************************************/
/*
 * @file types.h
 *
 * The types.h file contains the type definitions for datatypes used by ATTX in 
 * clockwerk and derived repositories, such as warptwin and warpOS. The types
 * defined in this file generally must be defined in any derived or modified 
 * applications.
*/
#ifndef TYPES_H
#define TYPES_H

#include <stdint.h>
#include "core/half.hpp"

// STANDARD TYPES FOR INTEGERS
// The following code block defines aliases for integer types which are
// used in clockwerk. These types should be used everywhere in lieu
// of standard integer types
using int8 = int8_t;
using int16 = int16_t;
using int32 = int32_t;
using int64 = int64_t;
using uint8 = uint8_t;
using uint16 = uint16_t;
using uint32 = uint32_t;
using uint64 = uint64_t;
using float16 = half_float::half;

// STANDARD TYPE FOR FLOATING POINT
// The floating_point variable defines the floating point type to be used 
// in clockwerk and warpOS. It is used to standardize floating point variable
// use and prevent the need for templated types
using floating_point = double;

#endif