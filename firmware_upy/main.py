from machine import Pin
import time

# Sleep a bit longer in init to ensure it gets set right.
SHIFT_REGISTER_INIT_SLEEP_MS = 100

# Sleep time between each bit shift.
SHIFT_REGISTER_SLEEP_US = 2000

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


def init_shift_register() -> None:
    """Initialize shift register pins to default states."""
    # Clear shift register.
    PIN_SHIFT_N_SRCLR.value(0)
    time.sleep_ms(SHIFT_REGISTER_INIT_SLEEP_MS)
    PIN_SHIFT_N_SRCLR.value(1)  # Active low, so set to normal (not clearing).
    time.sleep_ms(SHIFT_REGISTER_INIT_SLEEP_MS)

    PIN_SHIFT_N_OE.value(0)  # Active low, set low to enable outputs
    PIN_SHIFT_SRCK.value(0)  # Clock starts low
    PIN_SHIFT_RCLK.value(0)  # Latch starts low

    # Wait for initialization to complete
    time.sleep_ms(SHIFT_REGISTER_INIT_SLEEP_MS)

    # Clear all outputs.
    set_shift_registers([False] * 48)
    time.sleep_ms(SHIFT_REGISTER_INIT_SLEEP_MS)


def set_shift_registers(data: list[bool]) -> None:
    """
    Set the state of all shift registers based on input data.

    Args:
        data: list of 48 boolean values representing desired output states
             (6 registers x 8 bits per register)
    """
    if len(data) != 48:
        raise ValueError("Data must contain exactly 48 boolean values")

    # Shift out all 48 bits
    for bit in reversed(data):  # Shift MSB first
        # Set data bit.
        PIN_SHIFT_SER_IN.value(1 if bit else 0)
        time.sleep_us(SHIFT_REGISTER_SLEEP_US)

        # Clock in the bit.
        PIN_SHIFT_SRCK.value(1)
        time.sleep_us(SHIFT_REGISTER_SLEEP_US)
        PIN_SHIFT_SRCK.value(0)
        time.sleep_us(SHIFT_REGISTER_SLEEP_US)

    # Latch the data to outputs
    PIN_SHIFT_RCLK.value(1)
    time.sleep_us(SHIFT_REGISTER_SLEEP_US)
    PIN_SHIFT_RCLK.value(0)
    time.sleep_us(SHIFT_REGISTER_SLEEP_US)


def basic_demo() -> None:
    print("All outputs off (high-impedance)")
    outputs = [False] * 48  # All outputs off
    set_shift_registers(outputs)
    time.sleep(2)

    print("All outputs on - positive")
    outputs = [(i % 2 == 0) for i in range(48)]  # Alternating on/off pattern
    set_shift_registers(outputs)
    time.sleep(2)

    print("All outputs on - negative")
    outputs = [(i % 2 == 1) for i in range(48)]  # Alternating on/off pattern
    set_shift_registers(outputs)
    time.sleep(2)

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
    DEBOUNCE_TIME_MS = 400

    if PIN_SW1.value() == 0:
        print(f"SW1 pressed. Activate all for {ACTION_TIME_MS} ms.")
        PIN_GP_LED_0.value(1)
        direction = "pos"

    elif PIN_SW2.value() == 0:
        print(f"SW2 pressed. Activate all for {ACTION_TIME_MS} ms.")
        PIN_GP_LED_1.value(1)
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
    PIN_GP_LED_0.value(0)
    PIN_GP_LED_1.value(0)

def demo_each_dot_one_by_one() -> None:
    for dot_num in range(24):
        print(f"Dot {dot_num} - Direction 1")
        shift_register_state = [False] * 48
        shift_register_state[dot_num] = True
        set_shift_registers(shift_register_state)
        time.sleep(1)

        print(f"Dot {dot_num} - Direction 2")
        shift_register_state = [False] * 48
        shift_register_state[dot_num + 1] = True
        set_shift_registers(shift_register_state)
        time.sleep(1)


def main() -> None:
    print("Starting init.")
    init_shift_register()
    PIN_GP_LED_0.value(0)
    PIN_GP_LED_1.value(0)
    print("Init complete.")

    while 0:
        print("Starting basic demo.")
        basic_demo()
        print("Basic demo complete.")


    while 1:
        print("Starting demo_each_dot_one_by_one().")
        demo_each_dot_one_by_one()

    print("Starting respond_to_buttons().")
    while 1:
        respond_to_buttons()


while True:
    main()
