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
OSAL header file

Author: Alex Reynolds
*/
#ifndef OS_SIM_LINUX_H 
#define OS_SIM_LINUX_H

#include "architecture/Time.h"
#include "flight/OS.h"

namespace warptwin {
// Ref. to sim exec which is essential for this guy here
class SimulationExecutive;

/**
 * @brief OS implementation for Linux
 * 
 * The OS implementation for Linux is designed to interact with the 
 * SimTimeManager and other simulation objects to provide simulated
 * outputs. Where sim parameters are not used, Linux I/O is used 
 * (i.e. for file i/o, cout, etc.)
 */
class SimLinux : public warpos::OS {
public:
    SimLinux() : OS() {}
    virtual ~SimLinux() {}

    /// @brief Set the simulation executive object on the simulated time
    /// @param exc The simulation executive
    void setExecutive(SimulationExecutive& exc) {_exc_ptr = &exc;}

    /**
     * @brief Retrieves a handle to the system base time.
     * 
     * The output of system time depends on whether time is not set (outputs time
     * from sim time manager) or time is set (outputs value which was set)
     * 
     * @return Pointer to a clockwerk::Time object representing the system time.
     */
    clockwerk::Time systemTime() override;

    /**
     * @brief Retrieves the system navigation time
     * @return A clockwerk::Time object representing the navigation time
     *
     * The navigation time is a universally achored form of time which is
     * synchronized between the flight vehicle and some ground reference.
     * Often used timesets include GPS time and UTC time. Though the specific
     * implementation varies system-to-system, these are generally stable
     * forms of time, whereas system time may drift over long periods.
     */
    clockwerk::Time navigationTime() override;

    /**
     * @brief Opens a file with the specified filename._sys_time
     * @param filename The name of the file to open.
     * @param desc Flags for how to open the file
     * @return File descriptor (int32) on success, or an error code if not implemented.
     */
    virtual int32 openFile(const char* filename, uint8 desc = static_cast<uint8>(warpos::file_descriptors_e::WRITE)
                                                            | static_cast<uint8>(warpos::file_descriptors_e::READ)
                                                            | static_cast<uint8>(warpos::file_descriptors_e::OPEN_ALWAYS)) override;
    /**
     * @brief Close the file at the file descriptor 
     * @param fd The file to close
     * @return NO_ERROR on success, error on failure
     */
    virtual int16 closeFile(int32 fd) override;
    /**
     * @brief Opens a file with the specified filename, used for reading.
     * @param fd File descriptor to check
     * @return File size
     */
    virtual uint32 fileSize(int32 fd) override;
    /**
     * @brief Writes data to an open file.
     * @param fd The file descriptor of the open file.
     * @param buffer Pointer to the data buffer to write.
     * @param size The number of bytes to write from the buffer.
     * @return Number of bytes written (int16), or an error code if not implemented.
     */
    virtual int16 writeFile(int32 fd, const char* buffer, uint32 size) override;
    /**
     * @brief Reads data from an open file.
     * @param fd The file descriptor of the open file.
     * @param buffer Pointer to the buffer where read data will be stored.
     * @param size The number of bytes to read into the buffer.
     * @return Number of bytes read (int16), or an error code if not implemented.
     */
    virtual uint32 readFile(int32 fd, char* buffer, int32 size) override;

    /**
     * @brief Opens a broadcast socket for sending data.
     * @details This function creates and opens a socket that can be used to send broadcast messages over the network.
     * @return Socket file descriptor (int32) on success, or an error code if not implemented.
     */
    virtual int32 openBroadcastSocket() override;
    /**
     * @brief Sends data over a broadcast socket.
     * @details Sends the specified buffer to the given address and port using the provided broadcast socket.
     * @param sock_fd The file descriptor of the broadcast socket.
     * @param address The destination address to send the broadcast to.
     * @param port The destination port number.
     * @param buffer Pointer to the data buffer to send.
     * @param len The number of bytes to send from the buffer.
     * @return Number of bytes sent (int16), or an error code if not implemented.
     */
    virtual int16 sendBroadcastSocket(int32 sock_fd, const char* address, uint32 port, const char* buffer, uint32 len) override;
    /**
     * @brief Opens a listener socket to receive data.
     * @details Creates and binds a socket to the specified address and port for listening to incoming data.
     * @param address The address to bind the listener socket to.
     * @param port The port number to bind the listener socket to.
     * @return Socket file descriptor (int32) on success, or an error code if not implemented.
     */
    virtual int32 openListenerSocket(const char* address, uint32 port) override;
    /**
     * @brief Reads data from a listener socket.
     * @details Reads up to max_len bytes from the specified listener socket into the provided buffer.
     * @param sock_fd The file descriptor of the listener socket.
     * @param buffer Pointer to the buffer where the received data will be stored.
     * @param max_len The maximum number of bytes to read into the buffer.
     * @return Number of bytes read (uint32), or an error code if not implemented.
     */
    virtual uint32 readListenerSocket(int32 sock_fd, char* buffer, uint32 max_len) override;

    /**
     * @brief Delay the current thread for a real wall-clock amount of time.
     * @details The base warpos::OS::delay() is an unimplemented stub (always
     * returns ERROR_BUFFER_NOT_IMPLEMENTED and does not block). Socket-relay
     * tests call delay() between a send and a read expecting the OS to have
     * actually delivered the datagram by the time they read it. Loopback UDP
     * delivery on Linux happens synchronously enough within sendto() that this
     * went unnoticed there; macOS's BSD network stack can deliver loopback
     * datagrams asynchronously, so an unimplemented delay() exposes a real race.
     * See KNOWN_ISSUES.md.
     * @param delay_time The amount of time to delay for
     * @return NO_ERROR on success
     */
    virtual int16 delay(const clockwerk::Time& delay_time) override;
protected:
    // Pointer to sim exec for timing stuff
    SimulationExecutive* _exc_ptr = nullptr;
};
}

#endif