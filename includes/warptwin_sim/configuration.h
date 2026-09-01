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
 * @file configuration.h
 *
 * The configuration.h file contains size definitions, including APIDs and other
 * variables which should be defined at compile time for clockwerk and other derived
 * tasks.
 * 
 * NOTE: The configuration.h file is one of several configuration files which exist
 * for different build targets. Each build target (e.g. cortexm7_freertos, unittest,
 * etc.) has its own configuration file. ALL CONFIGURATION FILES MUST HAVE THE SAME
 * CONTENT AND DEFINITIONS. This is to ensure consistency across different build
 * targets. When making changes to this file, ensure that the same changes are made
 * to all other configuration files.
*/

#ifndef CONFIGURATION_H
#define CONFIGURATION_H

#include "types.h"

////////////////////////////////////////////////////////////////////////////////////////
/// warpOS CONFIGURATION ITEMS
////////////////////////////////////////////////////////////////////////////////////////

/// @brief The maximum number of bytes which can be defined for a single telemetry packet
const uint16 CMD_TLM_PKT_MAX_SIZE_BYTES = 1000;  // Arbitrarily large

/// @brief The maximum number of bytes reserved for string implementation of a single tlm packet
const uint16 CMD_TLM_STR_MAX_SIZE_BYTES = 1000;  // Arbitrarily large

/// @brief The maximum number of bytes reserved for the normal priority telemetry queue
const uint16 TLM_NORMAL_PRI_QUEUE_SIZE_BYTES = 528;

/// @brief The maximum number of bytes reserved for the high priority telemetry queue
const uint16 TLM_HIGH_PRI_QUEUE_SIZE_BYTES = 128;

/// Max number of packets in the telemetry queue
const uint16 TLM_NORMAL_PRI_QUEUE_SIZE_PKTS = 100;

/// Max number of packets in the telemetry queue
const uint16 TLM_HIGH_PRI_QUEUE_SIZE_PKTS = 20;

/// Maximum number of entries in the telemetry table
const uint16 MAX_TLM_TABLE_SIZE = 100;

/// Max number of bytes which can be received and processed as
/// telemetry in the command manager (received onboard). Setting
/// this value to 0 effectively disables it
const uint16 RECEIVE_TLM_QUEUE_SIZE_BYTES = 10000;

/// Max number of packets which can be received and processed as
/// telemetry in the command manager (received onboard). Setting
/// this value to 0 effectively disables it
const uint16 RECEIVE_TLM_QUEUE_SIZE_PKTS = 100;

/// @brief The maximum number of characters reserved for a single telemetry field's
///        string buffer inside CMD_TLM_COMMON structs (required by Telemetry.h macros).
///        Matches the value used in warpos platform configuration.h files.
const uint16 MAX_TLM_FIELD_CHAR_BUF_SIZE = 128;

/// @brief The maximum number of UART Bytes the system will store
const uint16 MAXIMUM_UART_BYTES = 1000;

/// @brief The maximum number of NMEA Bytes the system buffer will store
const uint16 NMEA_MAX_BYTES = 82*2-1; // Max NMEA sentence length is 82, so double that minus 1 for safety

/// @brief This node's CSP (CubeSat Space Protocol) address on the onboard bus
const uint8 OCOMM_CSP_ADDRESS = 1;

/// @brief Maximum number of CSP ports apps may register with the onboard comms manager
const uint8 OCOMM_MAX_REGISTERED_PORTS = 16;

/// @brief Maximum number of CSP packets the onboard comms manager will route per scheduler step
const uint16 OCOMM_MAX_PACKETS_PER_STEP = 10;

/// @brief Maximum payload size (bytes) accepted for a single onboard CSP message
const uint16 OCOMM_MAX_PAYLOAD_BYTES = 256; 

/// @brief Number of telemetry payloads the onboard comms manager buffers between scheduler steps
const uint16 OCOMM_TLM_BUFFER_DEPTH = 16;

/// @brief Flag indicating whether the flight system is big endian or little endian
#define IS_BIG_ENDIAN false

/// @brief Seed for the CRC16 checksum
const uint32 CRC_SEED = 0xFFFFFFFF;

/// @brief Max amount of Files we can open
const uint8 MAX_FILES = 50; // * Note: this is an arbitrary limit. If this is changed, the IOC
                            // * FatFS value for concurrent values must also be changed

const uint16 MAXIMUM_LOG_BYTES = 1024; ///< Maximum number of bytes in the log buffer

/// @brief The maximum bytes to read from an SD card partition
const uint16 MAX_SD_READ = 511;

/// @brief The maximum amount of bytes a filename can be
const uint8 MAX_FILENAME = 128;

////////////////////////////////////////////////////////////////////////////////////////
/// CLOCKWERK CONFIGURATION ITEMS
////////////////////////////////////////////////////////////////////////////////////////

/// @brief The maximum number of children a warpOS app can have
const uint8 MAXIMUM_APP_CHILDREN = 50;

/// @brief The maximum number of children the flight executive can have
const uint8 MAXIMUM_FLIGHT_EXECUTIVE_CHILDREN = 200;

/// @brief The maximum number of characters in a graph tree object name
const uint8 MAXIMUM_NAME_CHARS = 40;

/// @brief The maximum depth a graph tree may reach, root counted as depth zero
/// @note Bounds every recursive walk of the tree so a malformed or unexpectedly deep
///       tree cannot exhaust the task stack. Must stay within the range of the rank
///       type (uint8), which GraphTreeObject static_asserts.
const uint8 MAXIMUM_TREE_DEPTH = 64;

/// @brief The maximum number of DataIO objects a single mapping chain may traverse
/// @note Bounds DataIOBase::read()/writePtr() so a cyclic or corrupted mapping returns
///       nullptr instead of recursing until the stack is exhausted.
const uint8 MAXIMUM_MAP_DEPTH = 32;

/// @brief The clockwerk_allow_vector flag allows the use of std::vector
///        in the code. This is not recommended for embedded systems when
///        deployed, but allows easier testing and simulation
#define CLOCKWERK_ALLOW_VECTOR 1

/// @brief The clockwerk_allow_std_string flag allows the use of std::string
///        in the code. This is not recommended for embedded systems when
///        deployed, but allows easier testing and simulation
#define CLOCKWERK_ALLOW_STD_STRING 1

////////////////////////////////////////////////////////////////////////////////////////
/// CODE COVERAGE UTILITIES
////////////////////////////////////////////////////////////////////////////////////////
// Code to exclude code from coverage utilities. 
// The ENABLE_COVERAGE flag is only defined via CMake when the -DCOVERAGE=ON, and 
// excludes code from being compiled with the Clang compiler and LLVM. This prevents
// certain code, such as safeDivide unreachable code or additional protection which 
// would not normally be excluded, to not compile and therefore not show up in statistics.
// To use, wrap:
// EXCLUDE_FROM_COVERAGE(
//     <code to exclude goes here>
// )
// Limitations: This utility cannot be used on code which would break if the code
// were not there. That is, it can be used for checks which should be excluded
// from coverage, but not unreachable math. For well-written code that shouldn't 
// be a problem.
// 
// THIS MACRO CANNOT BE USED WITHOUT APPROVAL OF THE CHIEF TECHNICAL AUTHORITY ON
// THE RELEVANT PROJECT AND APPROVAL OF REVIEWERS. IT SHOULD ONLY BE USED AS A LAST
// RESORT IN CASE CODE CANNOT BE REACHED BY NORMAL TESTING. IF CODE CAN BE TESTED
// IT SHOULD BE USED, RATHER THAN BEING WRAPPED
//
// WHEN THIS MACRO IS USED, IT MUST BE ACCOMPANIED BY A CODE COMMENT AT THE LOCATION
// OF ITS USE JUSTIFYING ITS USE, INCLUDING WHY THE ASSOCIATED CODE CANNOT 
// BE TESTED.
#ifndef ENABLE_COVERAGE
    #define EXCLUDE_FROM_COVERAGE(code) code
#else
    #define EXCLUDE_FROM_COVERAGE(code)
#endif

////////////////////////////////////////////////////////////////////////////////////////
/// PACKAGE CONFIGURATION ITEMS
////////////////////////////////////////////////////////////////////////////////////////
// Package-specific configuration constants land here (e.g. board/peripheral tuning
// values that don't belong in the shared warpOS configuration items above). This is a
// stepping stone: the long-term goal is porting all of configuration.h -- including this
// section -- into the manifest/generate.py tooling (with GUI support), but until that
// larger effort happens, add package-specific items directly here.

/// @brief Base APID for warptwin simulator-only packets
///
/// The sim harness needs a command APID but is not a warpOS app -- it has no manifest/builds
/// entry and no manifest/PacketDefinitions JSON, so utils/generate.py (which assigns
/// APP_APID_* sequentially as index * 0x010 from 0x000) never sees it and cannot hand it a
/// block. This one is therefore hand-reserved at the top of the 11-bit space, the last block
/// that generator would ever reach.
///
/// Living outside the manifest has two consequences, both intended for a sim-only backdoor:
/// utils/validatePacketFolder.py cannot see these values when it checks APID collisions, and
/// utils/buildWarpLinkCmdTlmJson.py will never emit them into the WarpLink cmd/tlm JSON.
/// Nothing in this block is ground-commandable. A packet that must reach a real ground
/// station does not belong here -- give it a PacketDefinitions entry instead.
const uint16 SIM_APID_BASE = 0x7F0;

/// @brief Command APID for setting a named simulation signal (cmd_sim in SimSetup.h).
///        Slot 0x00E preserves the 0x7FE wire value this command already used.
const uint16 CMD_APID_SIM_SET_SIGNAL = SIM_APID_BASE + 0x00E;

#endif
