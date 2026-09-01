/******************************************************************************
* Copyright (c) ATTX INC 2026. All Rights Reserved.
*
* This software and associated documentation (the "Software") are the 
* proprietary and confidential information of ATTX, INC. The Software is 
* furnished under a license agreement between ATTX and the user organization 
* and may be used or copied only in accordance with the terms of the agreement.
* Refer to 'license/attx_license.adoc' for standard license terms.
*
* EXPORT CONTROL NOTICE: THIS SOFTWARE MAY INCLUDE CONTENT CONTROLLED UNDER THE
* INTERNATIONAL TRAFFIC IN ARMS REGULATIONS (ITAR) OR THE EXPORT ADMINISTRATION 
* REGULATIONS (EAR99). No part of the Software may be used, reproduced, or 
* transmitted in any form or by any means, for any purpose, without the express 
* written permission of ATTX, INC.
******************************************************************************/
/*
Setup header file

Author: Alex Reynolds
*/
#ifndef PLATFORM_SIMSETUP_H
#define PLATFORM_SIMSETUP_H

#include <stdint.h>
#include <deque>
#include <vector>

#include "flight/OS.h"
#include "flight/Platform.h"
#include "flight/Setup.h"
#include "core/clockwerkerrors.h"
#include "flight/Packet.h"
#include "configuration.h"     // CMD_APID_SIM_SET_SIGNAL

namespace warptwin {

COMMAND(cmd_sim, CMD_APID_SIM_SET_SIGNAL, 200,
    ((std::array<char, 100>),   signal_name),   // The name of the signal to set
    ((std::array<char, 100>),   value)          // The value to set the signal to
) 

/**
 * @brief Holds the setup configuration for Flight Executive
 * 
 * The Setup class manages a set of base-level functionality, such as writing telemetry,
 * reading commands, etc. which are often hardware or low-level functions. It allows
 * users to specify which buffers are written for telemetry, for instance.
 * @note The telemetry and radio interfaces are currently hard-coded as the first and second
 * targets, respectively
 */
class SimSetup : public warpos::Setup {
public:
    /// @brief Calls openSysLog() as part of construction -- no HAL/device-mount ordering
    /// constraint here (unlike NucleoSetup/ExampleSetup), so there's nothing to defer.
    SimSetup(warpos::OS &os, warpos::Platform &platform);

    /// @brief Closes every socket this Setup opened
    ///
    /// Without this the listener sockets outlive their SimulationExecutive and stay
    /// bound to their ports for the life of the process. In a test binary that means
    /// the next executive's bind lands on a port an orphaned socket still holds --
    /// SO_REUSEPORT lets it succeed, and then the two sockets split the incoming
    /// datagrams between them, so traffic meant for the live executive is delivered to
    /// a dead one instead. Tests that pass alone then fail when run alongside others.
    ~SimSetup() override;

    /// @brief Initialize the telemetry buffer
    /// @return Error code corresponding to success/failure
    virtual int16 initTelemetryBuffer() override;
    /// @brief Write data to telemetry buffer
    /// @param target Device selection indicator. May be unused if telemetry only has one output
    /// @param data Pointer to the byte array to write
    /// @param size Size of the buffer pointed to by data
    /// @return Error code corresponding to success/failure
    /// @note The target parameter is treated as an index to the interface property arrays. 0
    /// corresponds to the ground station connection, and 1 corresponds to the radio connection
    virtual int16 writeTelemetry(uint8 target, uint8* data, uint16 size) override;

    /// @brief Initialize the command buffer
    /// @return Error code corresponding to success/failure
    virtual int16 initCommandBuffer() override;
    /// @brief Read data from the command buffer
    /// @param target Device selection indicator. May be unused if command only has one source
    /// @param data Pointer to the byte array to read
    /// @param max_size The maximum amount of data to read out of the buffer
    /// @return The number of bytes read out of the buffer
    /// @note The target parameter is treated as an index to the interface property arrays. 0
    /// corresponds to the ground station connection, and 1 corresponds to the radio connection
    virtual uint32 readCommand(uint8 target, uint8* data, uint32 max_size) override;

    /// @brief Write a system log line to stdout -- moved here from SimLinux, which used to
    /// implement it directly. Prints the sys_time it's given directly rather than re-deriving
    /// a timestamp through a SimulationExecutive pointer (that pointer's own systemTime()
    /// already derives from the same executive, so this drops a redundant second time source
    /// from the log path). See Setup::sysLog() for the base contract.
    virtual int16 sysLog(floating_point sys_time, const char* app, const char* message, uint16 msg_size) override;

    /// @brief Nothing to configure -- sysLog() above prints unconditionally, no destination to
    /// open. Exists (rather than falling back to the Setup base default) so this class follows
    /// the same "constructor calls openSysLog()" convention every other non-HAL-constrained
    /// Setup subclass does. Idempotent like every other override (trivially, since it has no
    /// state to double-open).
    virtual int16 openSysLog() override;

    /// @brief Set the IP address, telemetry port, and coommand port with WarpLink
    /// @brief Set the IP address, telemetry port, and command port for flight software running in warplink
    /// @param ip The IP address for interface with warplink. Default is internal routing
    /// @param tlm_port The port over which telemetry should be routed
    /// @param cmd_port The port over which commands should be routed
    /// @note This function sets the warplink interface for flight software apps running in warptwin
    void setFswWarpLinkInterface(std::string ip="127.0.0.1", uint32 tlm_port=5005, uint32 cmd_port=5006);

    /// @brief Set the upstream source from which warplink should receive telemetry
    /// @param ip IP address for the telemetry stream from warplink
    /// @param port Port for the telemetry stream from warplink
    /// @note This function sets the telemetry stream source from which warplink should receive data from external software
    void setWarpLinkTlmStreamSource(std::string ip="127.0.0.1", uint32 port=9000);

    /// @brief Set the upstream source from which warptwin should receive external commands
    /// @param ip IP address for the socket stream input
    /// @param port Port for the socket stream input
    /// @note This function sets the external source from which warptwin should receive external commands
    void setWarpLinkSimCmdSource(std::string ip="127.0.0.1", uint32 port=9000);

protected:
    /// @brief Drain all pending datagrams from a socket into a FIFO byte buffer
    /// @param sock_fd The socket file descriptor to read from
    /// @param fifo The deque to append received bytes into
    void _drainSocket(int32 sock_fd, std::deque<uint8>& fifo);

    int32 _tlm_sock = -1;
    int32 _cmd_sock = -1;
    int32 _stream_sock = -1;
    int32 _sim_cmd_sock = -1;

    // Params for interfacing with WarpLink
    char _fsw_ip[20] = "127.0.0.1";
    uint32 _fsw_tlm_port = 5005;
    uint32 _fsw_cmd_port = 5006;

    char _tlm_stream_ip[20] = "127.0.0.1";
    uint32 _tlm_stream_port = 9007;

    char _sim_cmd_ip[20] = "127.0.0.1";
    uint32 _sim_cmd_port = 9008;

    // Byte FIFOs — reassemble fragmented datagrams before handing data to callers
    static constexpr uint32 SOCKET_READ_SCRATCH_SIZE = 4096;
    std::deque<uint8> _stream_fifo;
    std::deque<uint8> _cmd_fifo;
    std::deque<uint8> _sim_cmd_fifo;
};
}

#endif