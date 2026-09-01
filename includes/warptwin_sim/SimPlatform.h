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
HAL header file

Author: Alex Reynolds
*/
#ifndef PACKAGE_SIMPLATFORM_H
#define PACKAGE_SIMPLATFORM_H

#include <stdint.h>

#include <string>

#include "architecture/Queue.hpp"
#include "core/clockwerkerrors.h"
#include "flight/Platform.h"

namespace warptwin {
        // Forward declaration only -- SimPlatform.cpp includes WarpWire.h, but this
        // header deliberately does not, so warpos-side code including SimPlatform.h
        // never needs warptwin's include path.
        class WarpWire;

        const uint32 QUEUE_SIZE = 1000; ///< Size of Queues
        const uint32 MAX_SIM_DEVICES = 16;  ///< Largest number of devices one platform can open

        /// Largest single message a device channel can carry. Must be at least
        /// WARPWIRE_WIRE_CAPACITY_BYTES; a larger message is reported as an
        /// error by the receive path rather than truncated.
        const uint32 SIM_DEVICE_MAX_MSG_BYTES = 256;

        /// First file descriptor handed out by an open*() call. Sits clear of the
        /// clockwerk error codes (all well under 1000), which the Platform interface
        /// also returns through the same int32 return value -- so no valid descriptor
        /// can be mistaken for an error code, or the reverse.
        const int32 SIM_DEVICE_FD_BASE = 1000;

        /// Suffixes appended to a device name to form its channel pair. Named from
        /// flight software's point of view: it writes the "_write" channel and reads
        /// the "_read" one, matching the *_write_buffer/*_read_buffer arrangement
        /// this platform used before it exchanged bytes over WarpWire.
        const char SIM_DEVICE_WRITE_SUFFIX[] = "_write";
        const char SIM_DEVICE_READ_SUFFIX[] = "_read";

/**
 * @brief A sim-side model standing in for the hardware on the far end of a bus
 *
 * Implemented by a model that has to answer a transaction the way a real part
 * would: synchronously, and as a function of the bytes just clocked in. The
 * channel transports cannot do that -- a channel latches one message and moves
 * it only when the owning ExternalInterfaceModel syncs, so a driver issuing
 * several transactions within one of its own steps would overwrite all but the
 * last and read replies belonging to the step before. A handler is called
 * in-line instead, from inside the platform call the driver made.
 *
 * Handlers are registered by device name, so registration works whether the
 * model or flight software opened the device first.
 *
 * @note A handler runs in this process by construction, so a device answered
 *       this way cannot also be routed over a socket or shared memory.
 */
class SimDeviceHandler {
public:
    virtual ~SimDeviceHandler() {}

    /// @brief Answer one full-duplex SPI transaction
    /// @param mosi_ptr The bytes flight software clocked in
    /// @param miso_ptr Where the bytes clocked back out are written
    /// @param size Length of the transaction, in bytes
    /// @return Error code corresponding to success/failure
    /// @note Callers may pass one buffer as both mosi_ptr and miso_ptr, which is
    ///       what a real full-duplex transfer does. An implementation must
    ///       therefore read each byte of mosi_ptr before writing the same index
    ///       of miso_ptr.
    virtual int16 transact(const uint8 *mosi_ptr, uint8 *miso_ptr, uint16 size)
        {return ERROR_BUFFER_NOT_IMPLEMENTED;}

    /// @brief Accept one I2C write transaction addressed to this part
    /// @param buffer_ptr The bytes flight software put on the bus
    /// @param size Number of bytes written
    /// @return Error code corresponding to success/failure
    /// @note I2C is half duplex, so a register read arrives as a write naming the
    ///       register followed by a separate readI2C(). Holding the register
    ///       pointer between the two is the handler's job, exactly as the real
    ///       part holds it -- SimPlatform keeps no state of its own.
    virtual int16 writeI2C(const uint8 *buffer_ptr, uint32 size)
        {return ERROR_BUFFER_NOT_IMPLEMENTED;}

    /// @brief Answer one I2C read transaction addressed to this part
    /// @param buffer_ptr Where the bytes clocked out are written
    /// @param size Number of bytes flight software is reading
    /// @return Error code corresponding to success/failure
    virtual int16 readI2C(uint8 *buffer_ptr, uint32 size)
        {return ERROR_BUFFER_NOT_IMPLEMENTED;}
};

/// Registered against a handler that answers for a whole bus rather than one
/// address on it. SPI has no addressing, so its handlers always use this
static const uint16 SIM_DEVICE_NO_ADDRESS = 0xFFFF;

/// Largest I2C transaction the platform will frame, in bytes, memory address
/// included. Bounds the stack buffer writeI2CAddress()/readI2CAddress() build in
static const uint32 SIM_I2C_MAX_TRANSACTION_BYTES = 256;

/**
 * @brief One registered stand-in for a device's hardware
 */
struct SimDeviceHandlerEntry {
    std::string device_name;                    ///< Device name this handler answers for
    uint16 i2c_address = SIM_DEVICE_NO_ADDRESS; ///< Address on that bus, or SIM_DEVICE_NO_ADDRESS
    SimDeviceHandler *handler_ptr = nullptr;    ///< The handler itself, owned by its model
};

/**
 * @brief Which transport backs one direction of a device's channel pair
 */
enum device_connection_e {
    DEVICE_CONNECTION_NONE,     ///< Direction not wired up
    DEVICE_CONNECTION_BUFFER,   ///< Plain in-process buffer, opened by this platform
    DEVICE_CONNECTION_SHMEM,    ///< Shared memory, adopted from an existing channel
    DEVICE_CONNECTION_SOCKET    ///< Socket, adopted from an existing channel
};

/**
 * @brief One opened simulated device
 *
 * Holds the file descriptor flight software knows the device by, the WarpWire
 * channel carrying each direction, and the staging queue that turns WarpWire's
 * latched, whole-message channels back into the byte-accurate, consuming reads
 * the Platform interface promises.
 */
struct SimDevice {
    int32 fd = -1;                          ///< Descriptor returned to flight software
    std::string device_name;                ///< The config's device field, as passed to open*()
    std::string write_channel;              ///< OUTPUT channel: flight software -> sim
    std::string read_channel;               ///< INPUT channel: sim -> flight software
    device_connection_e write_connection = DEVICE_CONNECTION_NONE;  ///< Transport backing write_channel
    device_connection_e read_connection = DEVICE_CONNECTION_NONE;   ///< Transport backing read_channel

    /// Bytes pulled off read_channel and not yet read by flight software
    clockwerk::Queue<uint8, QUEUE_SIZE> rx_queue;

    /// Last message pulled off read_channel, and its length. A channel latches
    /// its last message and re-presents it on every sync, so these are what
    /// distinguish a genuinely new message from the same one seen again.
    uint8 last_rx[SIM_DEVICE_MAX_MSG_BYTES] = {0};
    uint16 last_rx_size = 0;
};

/**
 * @brief WarpTwin-specific implementation of Platform
 *
 * The Sim platform is a specialized instance of platform designed
 * for hardware abstraction in sim world. Serial hardware interfaces (SPI,
 * UART, I2C) are redirected to WarpWire channels, allowing flexible mapping
 * of interface to models on or off the simulation host system: whatever a
 * device's channel pair is backed by -- a plain in-process buffer, shared
 * memory, or a socket -- is transparent to the flight software driving it.
 *
 * Each open*() call keys off its config's device field. If a channel of that
 * name is already registered on the WarpWire -- because a sim-side device
 * model wired one up over a socket or shared memory first -- this platform
 * adopts it; otherwise it opens a plain buffer channel. Either way the caller
 * gets back a file descriptor, and re-opening the same device name returns the
 * descriptor already assigned to it.
 *
 * GPIO pins are not devices in this sense (GpioConfig_t carries no device
 * name) and remain plain arrays, user-settable for read and inspectable for
 * write.
 *
 * @note Requires attachWarpWire() before any device can be opened;
 *       SimulationExecutive does this for the platform it owns.
 *
 * TODO: PWM, CAN, ADC, and hardware timers are not yet routed over WarpWire
 */
class SimPlatform : public warpos::Platform {
public:
    /// @brief Attach the WarpWire this platform exchanges all device traffic over
    /// @param wall_ptr The WarpWire to use, or nullptr to detach
    void attachWarpWire(WarpWire *wall_ptr) {_warp_wall_ptr = wall_ptr;}

    /// @brief Register a sim-side stand-in for a whole bus, for a device with no addressing
    /// @param device_name The device field the driver's config carries
    /// @param handler_ptr The handler answering for it, or nullptr to deregister
    /// @return Error code corresponding to success/failure
    /// @note Registering displaces any handler already held for that name, so a
    ///       model restarting does not consume a second slot. Once registered, the
    ///       device's transactions bypass its channel pair entirely.
    int16 registerDeviceHandler(const std::string &device_name, SimDeviceHandler *handler_ptr);

    /// @brief Register a sim-side stand-in for one part on an I2C bus
    /// @param device_name The device field the driver's config carries, i.e. the bus
    /// @param i2c_address The address that part answers to on that bus
    /// @param handler_ptr The handler answering for it, or nullptr to deregister
    /// @return Error code corresponding to success/failure
    /// @note Several parts can share one bus by registering different addresses.
    ///       Once any address on a bus is handled, a transaction to an address with
    ///       no handler is refused rather than falling back to the channel pair --
    ///       that is what a real bus does when nothing acknowledges.
    int16 registerDeviceHandler(const std::string &device_name, uint8 i2c_address,
                                SimDeviceHandler *handler_ptr);

    /// @brief Set the mode for a given GPIO pin on platform
	/// @param config GpioConfig_t object containing config info
    /// @return Error code corresponding to success/failure
    int16 setPinMode(const warpos::GpioConfig_t& config) override;
    /// @brief Write data value to a pin
    /// @param bank The bank on which to set the pin
    /// @param pin The pin to write
    /// @param value The value to write. Can be anything but typically HIGH/LOW
    /// @return Error code corresponding to success/failure
    int16 writePin(uint8 bank, uint32 pin, uint32 value) override;
    /// @brief Read data value from a pin
    /// @param bank The bank on which to set the pin
    /// @param pin The pin to read
    /// @param value Implicit return of the pin value
    /// @return Error code corresponding to success/failure
    int16 readPin(uint8 bank, uint32 pin, uint32 &value) override;

    /// @brief Open and configure SPI
    /// @param config The SPI config, whose device field names the channel pair
    /// @return File descriptor for the device, or an error code on failure
    virtual int32 openSPI(const warpos::SpiConfig_t& config) override;
    /// @brief Write and read a set of bytes via SPI
    /// @param spi_fd The device to write/read
    /// @param buffer The buffer to write from and read to
    /// @param size Number of bytes to write/read
    /// @return Error code corresponding to success/failure
    /// @note With a handler registered for this device, the transfer is genuinely full
    ///       duplex: the handler answers in-line, so what is read back is a reply to
    ///       the bytes this very call wrote. A driver may therefore issue a whole
    ///       sequence of transactions within one of its own steps.
    /// @note Without one, it is full duplex in name only. The response read back is
    ///       whatever the sim side published as of the last sync, not a reply to the
    ///       bytes just written -- those do not reach the sim side until the owning
    ///       ExternalInterfaceModel next executes. A driver issuing several
    ///       transactions per step will have all but the last overwritten.
    virtual int16 readWriteSPI(int32 spi_fd, uint8* buffer, uint8 size) override;

    /// @brief Open and configture UART connection
    /// @param config The UART config, whose device field names the channel pair
    /// @return File descriptor for the device, or an error code on failure
    virtual int32 openSerial(const warpos::UartConfig_t& config) override;
    /// @brief Write a byte to UART
    /// @param device_fd The file descriptor of the device to write
    /// @param buffer The buffer of values to write
    /// @param size The number of bytes to write
    /// @return Error code corresponding to success/failure
    virtual int16 writeSerial(int32 device_fd, uint8* buffer, uint8 size) override;
    /// @brief Read a byte from UART
    /// @param device_fd File descriptor of the device to read
    /// @param buffer Implicit return of values read from buffer
    /// @param size The number of bytes to read
    /// @return The number of bytes read
    virtual uint32 readSerial(int32 device_fd, uint8* buffer, uint32 size) override;
    /// @brief Check number of bytes ready to read on UART
    /// @param device_fd The file descriptor of the device to check
    /// @return Number of bytes available
    virtual uint32 bytesReadySerial(int32 device_fd) override;

    /// @brief Open an I2C device
    /// @param config The I2C config, whose device field names the channel pair
    /// @return File descriptor for the device, or an error code on failure
    /// @note THIS FUNCTION CURRENTLY ASSUMES I2C IS CONFIGURED BY IOC OUTSIDE OF CODE
    virtual int32 openI2C(const warpos::I2cConfig_t& config) override;
    /// @brief Write a byte to I2C
    /// @param i2c_fd The file descriptor to write
    /// @param i2c_address The address to write
    /// @param buffer The buffer of values to write
    /// @param size The number of bytes to write
    /// @return Error code corresponding to success/failure
    /// @note With handlers registered on this bus, i2c_address selects which one the
    ///       transaction goes to, so several parts share one device name. Addressing
    ///       a part that is not on the bus is refused rather than carried, which is
    ///       what a real bus does when nothing acknowledges.
    /// @note Without any, i2c_address is ignored and everything on the bus shares the
    ///       one channel pair the device name owns -- so two addresses cannot be told
    ///       apart, and that case needs a device per address.
    /// @note I2C is half duplex, so a register read is this call naming the register
    ///       followed by a separate readI2C(). Whatever holds the register pointer
    ///       between the two does so itself; the platform keeps no such state.
    virtual int16 writeI2C(int32 i2c_fd, uint8 i2c_address, uint8* buffer, uint8 size) override;
    /// @brief Read a byte from I2C
    /// @param i2c_fd The file descriptor to read
    /// @param i2c_address the address of the I2C device
    /// @param buffer Implicit return of values read from buffer
    /// @param size The number of bytes to read
    /// @return Error code corresponding to success/failure
    /// @note Addressing behaves as described on writeI2C(). The bytes returned come
    ///       from whatever the addressed part last had pointed at, so this is normally
    ///       preceded by the writeI2C() that names it.
    virtual int16 readI2C(int32 i2c_fd, uint8 i2c_address, uint8* buffer, uint32 size) override;
    /// @brief Write a buffer of data to an I2C address
    /// @param i2c_fd The file descriptor to write
    /// @param i2c_address The I2C address to communicate with
    /// @param mem_address The memory address to communicate with
    /// @param buffer The buffer of data to write
    /// @param size The amount of data (not including address) to write
    /// @param memory_16 Boolean if the memory addresses are 16 bit or 8 bit, default to false (8 bit)
    /// @return Error code corresponding to success/failure
    /// @note mem_address leads the payload, most significant byte first, and the two go
    ///       out as one uninterrupted write -- which is what distinguishes this from
    ///       calling writeI2C() twice. Addressing behaves as described on writeI2C().
    virtual int16 writeI2CAddress(int32 i2c_fd, uint8 i2c_address, uint32 mem_address, uint8* buffer, uint32 size, bool memory_16 = false) override;
    // @brief Write a buffer of data to an I2C address
    /// @param i2c_fd The file descriptor to write
    /// @param i2c_address The I2C address to communicate with
    /// @param mem_address The memory address to communicate with
    /// @param buffer The buffer of data to read to
    /// @param size The maximum amount of data (not including address) to read
    /// @param memory_16 Boolean if the memory addresses are 16 bit or 8 bit, default to false (8 bit)
    /// @return Error code corresponding to success/failure
    /// @note Issues the write naming mem_address, most significant byte first, then the
    ///       read -- the two phases of the real transaction. Addressing behaves as
    ///       described on writeI2C().
    virtual int16 readI2CAddress(int32 i2c_fd, uint8 i2c_address, uint32 mem_address, uint8* buffer, uint32 size, bool memory_16 = false) override;

    /// @brief Open a PWM channel
    /// @param config PWM configuration object
    /// @return Error code corresponding to success/failure
    virtual int16 openPwmChannel(warpos::PwmConfig_t& config) override;
    /// @brief Write a buffer of data to an I2C address
    /// @param pwm_fd The file descriptor to write
    /// @param channel the Channel to write to
    /// @param value The value to write
    /// @return Error code corresponding to success/failure
    virtual int16 writePwm(int32 pwm_fd, uint8 channel, uint32 value) override;

    /// @brief Look up an opened device by descriptor
    /// @param device_fd The descriptor returned by an open*() call
    /// @return The device, or nullptr if device_fd was never opened
    /// @note For tests and debugging -- reports which channels a device ended up
    ///       on and what each direction is backed by.
    const SimDevice* findDevice(int32 device_fd);

    // Test buffers to manage read/write and value inputs/outputs
    uint8 pin_modes[100] = {0};                                 // Records pin mode
    uint16 pin_write[100] = {0};                                // Records write output from fc
    uint16 pin_read[100] = {0};                                 // User settable -- is read by fc
    uint32 speed[100] = {0};                                    // Speed for output pins (not always used)
    uint32 pull[100] = {0};                                     // Sets pull (up/down/no) for the selected pin
    uint32 alternate[100] = {0};                                // Sets alternate function for the pin

protected:
    /// @brief Open (or return the already-open) device for a config's device name
    /// @param device_name The device field from the protocol's config struct
    /// @return File descriptor for the device, or an error code on failure
    int32 _openDevice(const char* device_name);

    /// @brief Adopt an existing channel of this name, or open a plain buffer one
    /// @param channel_name The channel to adopt or open
    /// @param mode_output true to open an OUTPUT channel, false for INPUT
    /// @param out_connection The transport the channel ended up on
    /// @return Error code corresponding to success/failure
    int16 _adoptOrOpenChannel(const std::string& channel_name, bool mode_output,
                              device_connection_e& out_connection);

    /// @brief Find an opened device by its descriptor
    /// @param device_fd The descriptor to look up
    /// @return The device, or nullptr if device_fd was never opened
    SimDevice* _findDeviceByFd(int32 device_fd);

    /// @brief Find an opened device by the name it was opened under
    /// @param device_name The device name to look up
    /// @return The device, or nullptr if device_name was never opened
    SimDevice* _findDeviceByName(const char* device_name);

    /// @brief Lay a memory address into a buffer ahead of its payload
    /// @param mem_address The address to frame
    /// @param memory_16 true for a 16 bit address, false for 8 bit
    /// @param out_ptr Buffer receiving the address bytes, most significant first
    /// @return Number of bytes written
    int16 _frameMemAddress(uint32 mem_address, bool memory_16, uint8 *out_ptr);

    /// @brief Record a handler against a device name and address
    /// @param device_name The device field the driver's config carries
    /// @param i2c_address The address on that bus, or SIM_DEVICE_NO_ADDRESS
    /// @param handler_ptr The handler answering for it, or nullptr to deregister
    /// @return Error code corresponding to success/failure
    /// @note Both public overloads land here. Kept separate from them because a
    ///       uint16 public overload would swallow the uint8 one's own delegation.
    int16 _registerDeviceHandler(const std::string &device_name, uint16 i2c_address,
                                 SimDeviceHandler *handler_ptr);

    /// @brief Find the handler standing in for a device's hardware
    /// @param device_name The device name to look up
    /// @param i2c_address The address to look up, or SIM_DEVICE_NO_ADDRESS for a
    ///                    device whose bus has no addressing
    /// @return The handler, or nullptr if nothing is registered for that pair
    SimDeviceHandler* _findHandler(const std::string &device_name,
                                   uint16 i2c_address = SIM_DEVICE_NO_ADDRESS);

    /// @brief Report whether any handler at all is registered against a bus
    /// @param device_name The device name to look up
    /// @return true if some address on this bus is handled
    /// @note Distinguishes an unhandled bus, which still falls back to its channel
    ///       pair, from a handled bus being addressed where nothing answers.
    bool _busHasHandler(const std::string &device_name);

    /// @brief Route an I2C transaction to the handler for one address on a bus
    /// @param i2c_fd The descriptor of the device being addressed
    /// @param i2c_address The address on that bus
    /// @param out_handler_ptr Receives the handler, or nullptr if the bus is unhandled
    /// @return NO_ERROR if the caller should proceed, otherwise the error to return
    int16 _findI2CHandler(int32 i2c_fd, uint8 i2c_address, SimDeviceHandler *&out_handler_ptr);

    /// @brief Move anything newly arrived on a device's read channel into its rx queue
    /// @param device The device to drain
    /// @return Error code corresponding to success/failure
    /// @note A channel latches its last message, so this enqueues only when the
    ///       message differs from the one enqueued last. Two identical messages
    ///       in a row are therefore indistinguishable from one, and the duplicate
    ///       is dropped.
    int16 _drainReadChannel(SimDevice& device);

    /// @brief Write a buffer out on a device's write channel
    /// @param device_fd The descriptor of the device to write
    /// @param buffer The bytes to write
    /// @param size The number of bytes to write
    /// @return Error code corresponding to success/failure
    int16 _writeDevice(int32 device_fd, uint8* buffer, uint32 size);

    /// @brief Read bytes from a device's rx queue, draining its channel first
    /// @param device_fd The descriptor of the device to read
    /// @param buffer The buffer to read into
    /// @param size The maximum number of bytes to read
    /// @return The number of bytes read
    uint32 _readDevice(int32 device_fd, uint8* buffer, uint32 size);

    /// The WarpWire all device traffic is exchanged over, set by attachWarpWire()
    WarpWire* _warp_wall_ptr = nullptr;

    /// Devices opened so far, in the order they were opened
    SimDevice _devices[MAX_SIM_DEVICES];

    /// Number of entries in _devices that are in use
    uint32 _device_count = 0;

    /// Handlers standing in for device hardware. Held separately from _devices
    /// rather than on it, since a handler may register before flight software
    /// has opened the device it answers for
    SimDeviceHandlerEntry _handlers[MAX_SIM_DEVICES];

    /// Number of entries in _handlers that are in use
    uint32 _handler_count = 0;
};
}

#endif
