# mpremote connect <port_path> mip install github:josverl/micropython-stubs/mip/typing.mpy

from typing import Literal

from machine import I2C, Pin
import time
import json

from ina219 import INA219

# Pin definitions for shift register control.
PIN_SHIFT_SER_IN = Pin(2, Pin.OUT)  # GP2: Serial data input
PIN_SHIFT_SRCK = Pin(3, Pin.OUT)  # GP3: Shift register clock
PIN_SHIFT_N_SRCLR = Pin(4, Pin.OUT)  # GP4: Shift register clear
PIN_SHIFT_RCLK = Pin(5, Pin.OUT)  # GP5: Register clock (latch)
PIN_SHIFT_N_OE = Pin(6, Pin.OUT)  # GP6: Output enable

# Constants for setting the state of the shift registers.
DOT_ADDITION_CONSTANT_UP = 0
DOT_ADDITION_CONSTANT_DOWN = 1
DOT_ADDITION_CONSTANTS = {
    "up": DOT_ADDITION_CONSTANT_UP,
    "down": DOT_ADDITION_CONSTANT_DOWN,
}

# Pin definitions for general purpose LEDs and buttons.
PIN_SW1 = Pin(28, Pin.IN, Pin.PULL_UP)
PIN_SW2 = Pin(27, Pin.IN, Pin.PULL_UP)
PIN_GP_LED_0 = Pin(7, Pin.OUT)
PIN_GP_LED_1 = Pin(8, Pin.OUT)

# Pin/Peripheral Init: INA219 Current Sensor.
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

    fast_clear_shift_register()

    # Clear all outputs explicity (as a precaution).
    set_shift_registers([False] * 48)


def init() -> None:
    init_shift_register()

    # Print this message after clearing the shift registers.
    # Important to do them as fast as possible on startup.
    print("Starting init.")

    PIN_GP_LED_0.low()
    PIN_GP_LED_1.low()
    init_ina()
    print("Init complete.")


def reset() -> None:
    # CLI alias.
    init()


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


def fast_clear_shift_register() -> None:
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

    # Do 24 bits twice, so that when using only a single board,
    # its outputs are cleared first.
    for _ in range(2):
        # Shift out LOW bits (fastest possible method)
        for _ in range(24):
            srck_set(1)
            srck_set(0)

        # Latch the data to outputs
        rclk_set(1)
        rclk_set(0)


def set_all_to_each_state(
    duration_each_state_ms: int = 500, pause_duration_ms: int = 100
) -> None:
    for state in ("down", "up"):
        print(f"Setting all outputs to {state}.")

        outputs = [(i % 2 == DOT_ADDITION_CONSTANTS[state]) for i in range(48)]
        set_shift_registers(outputs)
        sleep_ms_and_log_ina_json(duration_each_state_ms)

        # Pause for a sec with outputs off.
        fast_clear_shift_register()

        if state == "down":
            time.sleep_ms(pause_duration_ms)


def set_dot(
    dot_num: int, direction: Literal["up", "down"], duration_ms: int = 0
) -> None:
    register_state = [False] * 48
    register_state[dot_num * 2 + DOT_ADDITION_CONSTANTS[direction]] = True

    set_shift_registers(register_state)

    sleep_ms_and_log_ina_json(duration_ms, log_period_ms=int(round(duration_ms / 15)))

    fast_clear_shift_register()


def cycle_dot(
    dot_num: int, duration_ms: int = 0, count: int = 10, pause_ms: int = 1000
) -> None:
    for i in range(count):
        set_dot(dot_num, "down", duration_ms)
        time.sleep_ms(pause_ms)
        set_dot(dot_num, "up", duration_ms)
        time.sleep_ms(pause_ms)


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
    register_state[(dot_num * 2) + DOT_ADDITION_CONSTANTS[direction]] = True

    # print(f"Setting shift registers: {register_state}")
    set_shift_registers(register_state)

    sleep_ms_and_log_ina_json(
        ACTION_TIME_MS, log_period_ms=int(round(ACTION_TIME_MS / 15))
    )

    fast_clear_shift_register()
    print("Waiting for debounce.")
    time.sleep_ms(DEBOUNCE_TIME_MS)
    PIN_GP_LED_0.low()
    PIN_GP_LED_1.low()


def demo_each_dot_one_by_one() -> None:
    for dot_num in range(24):
        print(f"Dot {dot_num} - down")
        set_dot(dot_num, "down", duration_ms=1000)

        print(f"Dot {dot_num} - up")
        set_dot(dot_num, "up", duration_ms=1000)


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


def sleep_ms_and_get_ina_stats_mA(sleep_time_ms: int) -> dict[str, float]:
    start_time_ms = time.ticks_ms()
    current_values_mA = []
    while True:
        current_values_mA.append(ina.shunt_voltage * 1000 / INA_SHUNT_OMHS)
        current_time_ms = time.ticks_ms()
        elapsed_time_ms = time.ticks_diff(current_time_ms, start_time_ms)

        if elapsed_time_ms >= sleep_time_ms:
            break

    return {
        "min": min(current_values_mA),
        "max": max(current_values_mA),
        "avg": sum(current_values_mA) / len(current_values_mA),
        "data_points": len(current_values_mA),
    }


def minimum_measure_time() -> None:
    """Measure the minimum time it takes to log INA219 data."""
    start_time_us = time.ticks_us()
    pass
    end_time_us = time.ticks_us()
    duration_us = time.ticks_diff(end_time_us, start_time_us)
    print(f"Minimum measure time: {duration_us} us.")


def self_test_each_dot(duration_per_dot_ms: int = 10) -> None:
    dot_pass_list = []
    dot_fail_list = []
    for dot_num in range(24):
        dot_failed = False

        for direction in ("down", "up"):
            print(f"Dot {dot_num} - {direction}")
            register_state = [False] * 48
            register_state[dot_num * 2 + DOT_ADDITION_CONSTANTS[direction]] = True
            set_shift_registers(register_state)
            stats_mA = sleep_ms_and_get_ina_stats_mA(duration_per_dot_ms)
            print(f"    Stats (mA): {json.dumps(stats_mA)}")
            if stats_mA["max"] < 20:
                print(f"WARNING: Dot #{dot_num} '{direction}' failed self-test.")
                dot_failed = True

        if dot_failed:
            dot_fail_list.append(dot_num)
        else:
            dot_pass_list.append(dot_num)

    print("Self-test complete.")
    print(f"Passing dots ({len(dot_pass_list)}): {dot_pass_list}")
    print(f"Failing dots ({len(dot_fail_list)}): {dot_fail_list}")


def self_test_lights_and_buttons() -> None:
    print("Testing lights and buttons.")
    print("Press SW1 to turn on GP_LED_0.")
    print("Press SW2 to turn on GP_LED_1.")
    print("Press both to exit.")

    last_sw1 = 1
    last_sw2 = 1

    while 1:
        sw1 = PIN_SW1.value()
        sw2 = PIN_SW2.value()

        if sw1 != last_sw1:
            last_sw1 = sw1
            PIN_GP_LED_0.value(not sw1)
            print(f"SW1: {sw1}")

        if sw2 != last_sw2:
            last_sw2 = sw2
            PIN_GP_LED_1.value(not sw2)
            print(f"SW2: {sw2}")

        if sw1 == 0 and sw2 == 0:
            PIN_GP_LED_0.low()
            PIN_GP_LED_1.low()
            print("Both buttons pressed. Exiting.")
            break

        time.sleep_ms(100)


def print_available_commands() -> None:
    print("""
Available commands:
    - help()
    - init(), reset()
        -> Initialize the shift registers and INA219.
    - set_all_to_each_state(duration_each_state_ms: int = 500, pause_duration_ms: int = 100) -> None
        -> Set all outputs to each state in turn, starting with high-impedance, then down, then up.
    - self_test_each_dot(duration_per_dot_ms: int = 10) -> None
        -> Test each dot by setting it to down and up for a short duration.
        -> Prints a list of passing and failing dots, based on those that draw current.
    - self_test_lights_and_buttons()
    - set_dot(dot_num: int, direction: "up"/"down", duration_ms: int = 0) -> None:
    - cycle_dot(dot_num: int, duration_ms: int = 0, count: int = 10, pause_ms: int = 1000) -> None:
    - <just a single period>
        -> Repeat the last command.
    """)


def help() -> None:
    print_available_commands()


# Set some helpful local aliases.
up = "up"
down = "down"
dn = "down"
dwn = "down"
pos = "up"
neg = "down"


class GlobalStoreSingleton:
    def __init__(self):
        self.last_command = "help"


global_store = GlobalStoreSingleton()


def prompt_and_execute() -> None:
    print("Enter a command, or use 'help':")
    command = input(">> ").strip()

    if command == ".":
        print("Repeating last command.")
        command = global_store.last_command
    else:
        command = command.strip()
        global_store.last_command = command  # Store for repeat feature.

    # If the command does not have parentheses, add them.
    if "(" not in command and ")" not in command:
        command += "()"

    print(f"Executing command: {command}\n")

    try:
        exec(command)
    except Exception as e:
        print(f"Error: {e}")
    print()


def main() -> None:
    init()

    minimum_measure_time()

    while 1:
        prompt_and_execute()

    # Await button press to start demo.
    print("Awaiting button press to start demo.")
    while PIN_SW1.value() and PIN_SW2.value():
        pass
    print("Button press detected. Starting demo.")
    time.sleep_ms(1000)  # Debounce.


while True:
    main()
