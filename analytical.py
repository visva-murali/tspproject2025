import numpy as np

#create 200 length array 
#then code the signal timing plan into the the array for each approach 
#then change it as appropriate 


#needed variables
signal_timing = [
    {'phase': 'East-West Through', 'duration': 34},
    {'phase': 'East-West Through Yellow', 'duration': 3.8},
    {'phase': 'East-West Through Red Clearance', 'duration': 2.2},
    {'phase': 'North-South Left', 'duration': 5},
    {'phase': 'North-South Left Yellow', 'duration': 3.6},
    {'phase': 'North-South Left Red Clearance', 'duration': 1.2},
    {'phase': 'North-South Through', 'duration': 34.5},
    {'phase': 'North-South Through Yellow', 'duration': 3.6},
    {'phase': 'North-South Through Red Clearance', 'duration': 1.9},
    {'phase': 'East-West Left', 'duration': 5},
    {'phase': 'East-West Left Yellow', 'duration': 3.8},
    {'phase': 'East-West Left Red Clearance', 'duration': 1.2},
]
# arrival_time = 10 #red tsp strategy
arrival_time = 85

#variables needed for delay
arrival_rate_nb = 3
arrival_rate_ns = 3   # per second
arrival_rate_eb = 2  
arrival_rate_wb = 2 # per second

#use effective greentime 

diss_rate_nb = 2
diss_rate_sb = 2  # per second (during green start up)
diss_rate_eb = 1
diss_rate_wb = 1  # per second (during green start up)


#identifies which phase the bus is in based on the arrival time 
def find_bus_phase(arrival_time, signal_timing):
    """
    Determine which phase the bus will arrive at based on its arrival time,
    how many seconds are left in the phase when the bus arrives, and the phase status 
    (whether it's Green, Yellow, or Red clearance).

    Parameters:
    arrival_time (float): The arrival time of the bus in seconds.
    signal_timing (list): A list of dictionaries representing the signal timing plan.
    
    Returns:
    tuple: A tuple containing the phase name, seconds left in the phase, and the phase status.
    """
    # Initialize the cumulative time
    cumulative_time = 0

    # Iterate through each phase to determine where the arrival time fits
    for phase in signal_timing:
        phase_duration = phase['duration']
        
        # Check if the arrival time is within this phase
        if cumulative_time <= arrival_time < cumulative_time + phase_duration:
            # Calculate the remaining time in this phase
            remaining_time = cumulative_time + phase_duration - arrival_time
            
            # Determine the phase status (Green, Yellow, Red Clearance)
            if 'Yellow' in phase['phase']:
                status = 'Yellow'
            elif 'Red Clearance' in phase['phase']:
                status = 'Red Clearance'
            else:
                status = 'Green'

            return (phase['phase'], remaining_time, status)
        
        # Update cumulative time
        cumulative_time += phase_duration

    # If the arrival time is outside the full cycle, return a message indicating it's not valid
    return "Arrival time is outside the full cycle."

phase, remaining_time, status = find_bus_phase(arrival_time, signal_timing)
print(f"The bus will arrive at the {phase} phase with {remaining_time} seconds left.")

def check_tsp_need(phase, remaining_time):
    """
    Determine if TSP is needed based on the phase and remaining time.

    Parameters:
    phase (str): The phase name.
    remaining_time (float): The remaining time in the phase when the bus arrives.

    Returns:
    str: A message indicating if TSP is needed.
    """
    if phase == 'North-South Through':
        return "Bus arrives during green, no adjustments needed"
    elif phase == 'North-South Through Yellow':
        return "Green Extension TSP is needed"
    else:
        return "Red TSP strategy is needed."
    
tsp_message = check_tsp_need(phase, remaining_time)
print(tsp_message)

#add by movement rather than direction (left and through)

def green_extension(signal_timing, max_extension=5):
    """
    Perform an exhaustive search that extends the green time for the North-South Through phase
    and reduces the green time for East-West Through phase to maintain a total cycle time of 100 seconds.

    Parameters:
    signal_timing (list): A list of dictionaries representing the signal timing plan.
    max_extension (int): The maximum extension for the North-South Through phase (1 to 5 seconds).
    
    Returns:
    list: A list of 5 modified signal timing plans.
    """
    # Extract relevant phases and their durations
    ns_through_index = next(i for i, phase in enumerate(signal_timing) if phase['phase'] == 'North-South Through')
    ew_through_index = next(i for i, phase in enumerate(signal_timing) if phase['phase'] == 'East-West Through')
    
    # Get the original durations
    ns_through_duration = signal_timing[ns_through_index]['duration']
    ew_through_duration = signal_timing[ew_through_index]['duration']
    
    modified_plans = []
    
    for extension in range(1, max_extension + 1):
        # Create a deep copy of the signal timing to avoid modifying the original data
        modified_plan = [phase.copy() for phase in signal_timing]
        
        # Calculate new durations
        new_ns = ns_through_duration + extension
        new_ew = ew_through_duration - extension
        
        # Update the durations in the copied plan
        modified_plan[ns_through_index]['duration'] = new_ns
        modified_plan[ew_through_index]['duration'] = new_ew
        
        modified_plans.append(modified_plan)
    
    return modified_plans


def print_signal_plans(plans):
    """Pretty print the modified signal plans."""
    for i, plan in enumerate(plans):
        print(f"Signal Plan {i+1}:")
        for phase in plan:
            print(f"  {phase['phase']}: {phase['duration']} seconds")
        print("-" * 50)


if tsp_message == "Green Extension TSP is needed":
    # Call the green_extension function to modify signal plans
    modified_plans = green_extension(signal_timing, max_extension=5)
    
    # Print the modified signal plans
    print_signal_plans(modified_plans)
else:
    print(tsp_message)



'''
def green_extension(signal_timing, max_extension=5):
    """
    Perform an exhaustive search that extends the green time for the North-South Through phase
    and reduces the green time for East-West Through phase to maintain a total cycle time of 100 seconds.

    Parameters:
    signal_timing (list): A list of dictionaries representing the signal timing plan.
    max_extension (int): The maximum extension for the North-South Through phase (1 to 5 seconds).
    
    Returns:
    list: A list of 5 modified signal timing plans.
    """
    # Extract relevant phases and their durations
    ns_through_index = next(i for i, phase in enumerate(signal_timing) if phase['phase'] == 'North-South Through')
    ew_through_index = next(i for i, phase in enumerate(signal_timing) if phase['phase'] == 'East-West Through')
    
    # Get the original durations
    ns_through_duration = signal_timing[ns_through_index]['duration']
    ew_through_duration = signal_timing[ew_through_index]['duration']
    total_cycle_time = sum(phase['duration'] for phase in signal_timing)
    
    # Perform the exhaustive search
    modified_plans = []
    
    for extension in range(1, max_extension + 1):
        # Calculate the new durations for the phases
        new_ns_through_duration = ns_through_duration + extension
        new_ew_through_duration = ew_through_duration - extension
        
        # Calculate the new total cycle time
        new_total_cycle_time = total_cycle_time - ns_through_duration - ew_through_duration + new_ns_through_duration + new_ew_through_duration
        
        # Ensure the total cycle time remains 100 seconds
        if new_total_cycle_time != 100:
            continue  # Skip invalid plans
        
        # Create a modified signal plan
        modified_plan = signal_timing.copy()
        modified_plan[ns_through_index]['duration'] = new_ns_through_duration
        modified_plan[ew_through_index]['duration'] = new_ew_through_duration
        
        modified_plans.append(modified_plan)
    
    return modified_plans


def print_signal_plans(plans):
    """Pretty print the modified signal plans."""
    for i, plan in enumerate(plans):
        print(f"Signal Plan {i+1}:")
        for phase in plan:
            print(f"  {phase['phase']}: {phase['duration']} seconds")
        print("-" * 50)


# Example usage:
signal_timing = [
    {'phase': 'East-West Through', 'duration': 34},
    {'phase': 'East-West Through Yellow', 'duration': 3.8},
    {'phase': 'East-West Through Red Clearance', 'duration': 2.2},
    {'phase': 'North-South Left', 'duration': 5},
    {'phase': 'North-South Left Yellow', 'duration': 3.6},
    {'phase': 'North-South Left Red Clearance', 'duration': 1.3},
    {'phase': 'North-South Through', 'duration': 34.5},
    {'phase': 'North-South Through Yellow', 'duration': 3.6},
    {'phase': 'North-South Through Red Clearance', 'duration': 1.9},
    {'phase': 'East-West Left', 'duration': 5},
    {'phase': 'East-West Left Yellow', 'duration': 3.8},
    {'phase': 'East-West Left Red Clearance', 'duration': 1.3},
]

# Generate the green extension signal plans
modified_plans = green_extension(signal_timing, max_extension=5)

# Print the modified signal plans
print_signal_plans(modified_plans)
'''

'''
#delay calculations
def shockwave_delay(arrival_rate, dissipation_rate, traffic_flow, time_interval):
    """
    Calculate the vehicle delay using shockwave theory and queuing theory.
    
    Parameters:
    arrival_rate (float): The arrival rate of vehicles (vehicles per time unit).
    dissipation_rate (float): The dissipation rate (vehicles per time unit).
    traffic_flow (float): The current traffic flow (vehicles per time unit).
    time_interval (float): The time interval over which changes in traffic flow occur (seconds).
    
    Returns:
    float: The average delay per vehicle (time units).
    """
    # Calculate the shockwave speed: Change in flow divided by the time interval
    delta_flow = traffic_flow - arrival_rate  # Net change in flow
    shockwave_speed = delta_flow / time_interval  # Shockwave speed
    
    # Calculate the queue length based on the arrival and dissipation rates
    queue_length = max(0, arrival_rate - dissipation_rate) * time_interval
    
    # Calculate the delay using shockwave theory
    delay = queue_length / max(shockwave_speed, 1e-6)  # Avoid division by zero if shockwave speed is too small
    
    delay = delay * 1.2

    return delay

# Northbound delay
def northbound_delay(arrival_rate, dissipation_rate, traffic_flow, time_interval):
    return shockwave_delay(arrival_rate, dissipation_rate, traffic_flow, time_interval)

# Southbound delay
def southbound_delay(arrival_rate, dissipation_rate, traffic_flow, time_interval):
    return shockwave_delay(arrival_rate, dissipation_rate, traffic_flow, time_interval)

# Eastbound delay
def eastbound_delay(arrival_rate, dissipation_rate, traffic_flow, time_interval):
    return shockwave_delay(arrival_rate, dissipation_rate, traffic_flow, time_interval)

# Westbound delay
def westbound_delay(arrival_rate, dissipation_rate, traffic_flow, time_interval):
    return shockwave_delay(arrival_rate, dissipation_rate, traffic_flow, time_interval)

# Example usage:
arrival_rate_north = 5  # Vehicles per second
arrival_rate_south = 6  # Vehicles per second
arrival_rate_east = 7  # Vehicles per second
arrival_rate_west = 4  # Vehicles per second

dissipation_rate = 2  # Vehicles per second (same for all directions)
traffic_flow_north = 6  # Vehicles per second (current flow northbound)
traffic_flow_south = 7  # Vehicles per second (current flow southbound)
traffic_flow_east = 8  # Vehicles per second (current flow eastbound)
traffic_flow_west = 5  # Vehicles per second (current flow westbound)

time_interval = 1  # Time interval in seconds

# Calculate delays for each direction
delay_north = northbound_delay(arrival_rate_north, dissipation_rate, traffic_flow_north, time_interval)
delay_south = southbound_delay(arrival_rate_south, dissipation_rate, traffic_flow_south, time_interval)
delay_east = eastbound_delay(arrival_rate_east, dissipation_rate, traffic_flow_east, time_interval)
delay_west = westbound_delay(arrival_rate_west, dissipation_rate, traffic_flow_west, time_interval)

print(delay_north)
print(delay_east)
print(delay_west)
print(delay_south)'
'''