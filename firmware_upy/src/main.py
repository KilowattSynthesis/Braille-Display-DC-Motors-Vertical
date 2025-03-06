# mpremote connect <port_path> mip install github:josverl/micropython-stubs/mip/typing.mpy

from typing import Literal

from machine import I2C, Pin
import time
import json

from ina219 import INA219

# Pin definitions for shift register control
PIN_SHIFT_SER_IN = Pin(2, Pin.OUT)  # GP2: Serial data input
PIN_SHIFT_SRCK = Pin(3, Pin.OUT)  # GP3: Shift register clock
PIN_SHIFT_N_SRCLR = Pin(4, Pin.OUT)  # GP4: Shift register clear
PIN_SHIFT_RCLK = Pin(5, Pin.OUT)  # GP5: Register clock (latch)
PIN_SHIFT_N_OE = Pin(6, Pin.OUT)  # GP6: Output enable

PIN_SW1 = Pin(28, Pin.IN, Pin.PULL_UP)
PIN_SW2 = Pin(27, Pin.IN, Pin.PULL_UP)
PIN_GP_LED_0 = Pin(7, Pin.OUT)
PIN_GP_LED_1 = Pin(8, Pin.OUT)

INA_SHUNT_OMHS = 0.300
ina_i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=100_000)
ina: INA219  # Constructed/initialized in `init_ina()`


def init_ina() -> None:
    """Initialize INA219 current sensor. Perform I2C scan."""
    print("Scanning I2C bus for INA219.")
    i2c_addr_list: list[int] = ina_i2c.scan()
    print(f"Found {len(i2c_addr_list)} devices: {i2c_addr_list}")

    if i2c_addr_list != [0x40]:
        raise ValueError("INA219 not found at expected address.")

    global ina
    ina = INA219(ina_i2c, addr=0x40)
    ina.set_calibration_32V_2A()


def init_shift_register() -> None:
    """Initialize shift register pins to default states."""
    # Clear shift register.
    PIN_SHIFT_N_SRCLR.low()
    PIN_SHIFT_N_SRCLR.high()  # Active low, so set to normal (not clearing).

    PIN_SHIFT_N_OE.low()  # Active low, set low to enable outputs
    PIN_SHIFT_SRCK.low()  # Clock starts low
    PIN_SHIFT_RCLK.low()  # Latch starts low

    # Clear all outputs.
    set_shift_registers([False] * 48)


def set_shift_registers(data: list[bool]) -> None:
    """
    Set the state of all shift registers based on input data.

    Args:
        data: list of 48 boolean values representing desired output states
             (6 registers x 8 bits per register)
    """
    start_time_us = time.ticks_us()
    if len(data) != 48:
        raise ValueError("Data must contain exactly 48 boolean values")

    # Precompute GPIO operations
    srck_set = PIN_SHIFT_SRCK.value
    ser_set = PIN_SHIFT_SER_IN.value
    rclk_set = PIN_SHIFT_RCLK.value

    # Shift out all 48 bits, MSB first
    for bit in reversed(data):
        ser_set(bit)
        srck_set(1)
        srck_set(0)

    # Latch the data to outputs
    rclk_set(1)
    rclk_set(0)

    end_time_us = time.ticks_us()
    duration_us = time.ticks_diff(end_time_us, start_time_us)
    print(f"Shift register set in {duration_us:,} us = {duration_us / 1000:.1f} ms.")


def fast_clear_shift_registers() -> None:
    """Clear all shift registers.

    Duration: 700us.
    """
    # This first block here should do it, but the Chinese knockoffs don't like it:
    # # Immediately clear all shift register storage bits
    # PIN_SHIFT_N_SRCLR.low()  # Assert active-low clear
    # time.sleep_us(1)  # Short delay to ensure clear is latched
    # PIN_SHIFT_N_SRCLR.high()  # Deassert clear

    # # Latch the cleared shift register into output
    # PIN_SHIFT_RCLK.high()
    # time.sleep_us(1)  # Ensure the latch registers the cleared values
    # PIN_SHIFT_RCLK.low()

    # Get direct access to `.value()` method for speed
    ser_set = PIN_SHIFT_SER_IN.value
    srck_set = PIN_SHIFT_SRCK.value
    rclk_set = PIN_SHIFT_RCLK.value

    # Ensure data line is LOW before shifting
    ser_set(0)

    # Shift out 48 LOW bits (fastest possible method)
    for _ in range(48):
        srck_set(1)
        srck_set(0)

    # Latch the data to outputs
    rclk_set(1)
    rclk_set(0)


def demo_set_all_to_each_state() -> None:
    print("All outputs off (high-impedance)")
    outputs = [False] * 48  # All outputs off
    set_shift_registers(outputs)
    sleep_ms_and_log_ina_json(2000)

    print("All outputs on - positive")
    outputs = [(i % 2 == 0) for i in range(48)]  # Alternating on/off pattern
    set_shift_registers(outputs)
    sleep_ms_and_log_ina_json(2000)

    print("All outputs on - negative")
    outputs = [(i % 2 == 1) for i in range(48)]  # Alternating on/off pattern
    set_shift_registers(outputs)
    sleep_ms_and_log_ina_json(2000)


def make_shift_register_list_of_cells(
    cell_states: list[tuple[str, str, str, str, str, str] | str],
) -> list[bool]:
    """Convert a list of cell states to a list of shift register states."""
    shift_register_state = [False] * 48

    for cell_number, cell_state in enumerate(cell_states):
        if isinstance(cell_state, str):
            cell_state = (
                cell_state,
                cell_state,
                cell_state,
                cell_state,
                cell_state,
                cell_state,
            )

        for dot_number, state in enumerate(cell_state):
            base_offset = cell_number * 6 * 2 + dot_number * 2
            in_a_in_b = {
                "brake": (True, True),
                "high-z": (False, False),
                "pos": (True, False),
                "neg": (False, True),
            }[state]
            shift_register_state[base_offset] = in_a_in_b[0]
            shift_register_state[base_offset + 1] = in_a_in_b[1]

    return shift_register_state


def respond_to_buttons() -> None:
    """Respond to the button presses by setting the state of all.

    * Pressing SW1 sets all to "pos" for a short time, then back to high-z.
    * Pressing SW2 sets all to "neg" for a short time, then back to high-z.
    """

    ACTION_TIME_MS = 250
    DEBOUNCE_TIME_MS = 650

    if PIN_SW1.value() == 0:
        print(f"SW1 pressed. Activate all for {ACTION_TIME_MS} ms.")
        PIN_GP_LED_0.high()
        direction = "pos"

    elif PIN_SW2.value() == 0:
        print(f"SW2 pressed. Activate all for {ACTION_TIME_MS} ms.")
        PIN_GP_LED_1.high()
        direction = "neg"

    else:
        return

    register_state = make_shift_register_list_of_cells([direction] * 4)
    # print(f"Setting shift registers: {register_state}")
    set_shift_registers(register_state)
    time.sleep_ms(ACTION_TIME_MS)
    set_shift_registers(make_shift_register_list_of_cells(["high-z"] * 4))
    print("Waiting for debounce.")
    time.sleep_ms(DEBOUNCE_TIME_MS)
    PIN_GP_LED_0.low()
    PIN_GP_LED_1.low()

def set_dot(dot_num: int, direction: Literal["up", "down"], duration_ms: int = 0) -> None:
    register_state = [False] * 48
    if direction == "down":
        register_state[dot_num * 2] = True
    elif direction == "up":
        register_state[dot_num * 2 + 1] = True

    set_shift_registers(register_state)

    sleep_ms_and_log_ina_json(
        duration_ms, log_period_ms=int(round(duration_ms / 15))
    )

    fast_clear_shift_registers()


def respond_to_buttons_single_dot(dot_num: int) -> None:
    """Respond to the button presses by setting the state of `dot_num`."""

    ACTION_TIME_MS = 1
    DEBOUNCE_TIME_MS = 400

    if PIN_SW1.value() == 0:
        PIN_GP_LED_0.high()
        direction = "down"
        print(f"SW1 pressed. Push Dot {dot_num} {direction} for {ACTION_TIME_MS} ms.")

    elif PIN_SW2.value() == 0:
        PIN_GP_LED_1.high()
        direction = "up"
        print(f"SW2 pressed. Push Dot {dot_num} {direction} for {ACTION_TIME_MS} ms.")

    else:
        return

    register_state = [False] * 48
    if direction == "down":
        register_state[dot_num * 2] = True
    elif direction == "up":
        register_state[dot_num * 2 + 1] = True

    # print(f"Setting shift registers: {register_state}")
    set_shift_registers(register_state)

    sleep_ms_and_log_ina_json(
        ACTION_TIME_MS, log_period_ms=int(round(ACTION_TIME_MS / 15))
    )

    fast_clear_shift_registers()
    print("Waiting for debounce.")
    time.sleep_ms(DEBOUNCE_TIME_MS)
    PIN_GP_LED_0.low()
    PIN_GP_LED_1.low()


def demo_each_dot_one_by_one() -> None:
    for dot_num in range(24):
        print(f"Dot {dot_num} - Direction 1")
        shift_register_state = [False] * 48
        shift_register_state[dot_num] = True
        set_shift_registers(shift_register_state)
        sleep_ms_and_log_ina_json(1000)

        print(f"Dot {dot_num} - Direction 2")
        shift_register_state = [False] * 48
        shift_register_state[dot_num + 1] = True
        set_shift_registers(shift_register_state)
        sleep_ms_and_log_ina_json(1000)


def log_ina_json(
    timestamp_ms: int | None = None,
    *,
    enable_fields: tuple[
        Literal["current_mA", "bus_voltage_mV", "shunt_voltage_mV"], ...
    ] = ("current_mA",),
) -> None:
    shunt_mV = ina.shunt_voltage * 1000

    data = {}

    if "current_mA" in enable_fields:
        data["current_mA"] = shunt_mV / INA_SHUNT_OMHS
    if "bus_voltage_mV" in enable_fields:
        data["bus_voltage_mV"] = ina.bus_voltage
    if "shunt_voltage_mV" in enable_fields:
        data["shunt_voltage_mV"] = shunt_mV

    if timestamp_ms is not None:
        data["timestamp_ms"] = timestamp_ms

    print(json.dumps(data))


def sleep_ms_and_log_ina_json(sleep_time_ms: int, log_period_ms: int = 250) -> None:
    start_time_ms = time.ticks_ms()

    while True:
        current_time_ms = time.ticks_ms()
        elapsed_time_ms = time.ticks_diff(current_time_ms, start_time_ms)

        if elapsed_time_ms >= sleep_time_ms:
            break  # Stop when the total sleep time has elapsed

        log_ina_json(elapsed_time_ms)

        # Calculate the remaining time
        next_log_time_ms = time.ticks_add(
            start_time_ms, elapsed_time_ms + log_period_ms
        )
        remaining_time_ms = time.ticks_diff(next_log_time_ms, time.ticks_ms())

        if remaining_time_ms > 0:
            time.sleep_ms(min(remaining_time_ms, sleep_time_ms - elapsed_time_ms))


def minimum_measure_time() -> None:
    """Measure the minimum time it takes to log INA219 data."""
    start_time_us = time.ticks_us()
    pass
    end_time_us = time.ticks_us()
    duration_us = time.ticks_diff(end_time_us, start_time_us)
    print(f"Minimum measure time: {duration_us} us.")


def prompt_and_execute() -> None:
    print("""
Available commands:
- exit()  # Doesn't really do anything.
- set_dot(dot_num: int, direction: "up"/"down", duration_ms: int = 0) -> None:
    """)

    print("Enter a command:")
    command = input(">>> ").strip()

    if command == "exit":
        print("Exiting.")
        return

    try:
        exec(command)
    except Exception as e:
        print(f"Error: {e}")

    print("Command executed.")

def main() -> None:
    print("Starting init.")
    init_shift_register()
    PIN_GP_LED_0.low()
    PIN_GP_LED_1.low()
    init_ina()
    print("Init complete.")

    minimum_measure_time()

    while 1:
        prompt_and_execute()
        

    # Await button press to start demo.
    print("Awaiting button press to start demo.")
    while PIN_SW1.value() and PIN_SW2.value():
        pass
    print("Button press detected. Starting demo.")
    time.sleep_ms(1000)  # Debounce.


    while 1:
        respond_to_buttons_single_dot(11)

    if 0:
        print("Starting basic demo.")
        demo_set_all_to_each_state()
        print("Basic demo complete.")

    while 1:
        print("Starting demo_each_dot_one_by_one().")
        demo_each_dot_one_by_one()

    print("Starting respond_to_buttons().")
    while 1:
        respond_to_buttons()


while True:
    main()
