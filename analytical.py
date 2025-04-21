def exhaustive_search_tsp(signal_timing, arrival_time, current_time=0, max_extension=5, optimization_horizon=200, avg_arrivals=None):
    """
    Perform an exhaustive search that tests applying TSP at every possible second
    of the traffic signal cycle to find optimal timing plans for a fixed bus arrival time.
    
    Parameters:
    signal_timing (list): A list of dictionaries representing the signal timing plan.
    arrival_time (int): The fixed arrival time of the bus in seconds.
    current_time (int): Current simulation time in seconds.
    max_extension (int): The maximum extension for TSP (in seconds).
    optimization_horizon (int): Time horizon for optimization in seconds.
    avg_arrivals (dict): Average vehicle arrivals per second for each direction.
    
    Returns:
    list: A list of modified signal timing plans with performance metrics.
    """
    # Set default average arrivals if not provided
    if avg_arrivals is None:
        avg_arrivals = {
            'north_south': 0.3,  # vehicles per second
            'east_west': 0.25    # vehicles per second
        }
        
    # Calculate total cycle length
    cycle_length = sum(phase['duration'] for phase in signal_timing)
    
    # Adjust arrival time based on current time
    adjusted_arrival_time = arrival_time - current_time if arrival_time >= current_time else arrival_time
    
    # Determine current position in the signal timing plan based on current_time
    current_phase_info = get_current_phase(current_time, signal_timing)
    if current_phase_info is None:
        current_phase_index, time_elapsed_in_phase = 0, 0
    else:
        current_phase_index, time_elapsed_in_phase = current_phase_info
    
    # Create a modified signal timing plan starting from current_time
    current_signal_timing = create_signal_plan_from_current_time(signal_timing, current_phase_index, time_elapsed_in_phase, optimization_horizon)
    
    # List to store all possible TSP timing plans
    tsp_plans = []
    
    # First, add a baseline "no TSP" plan
    baseline_plan = {
        'plan': current_signal_timing.copy(),
        'type': 'No TSP',
        'insertion_point': None,
        'extension': None,
        'bus_delay': calculate_bus_delay(current_signal_timing, adjusted_arrival_time),
        'person_delay': calculate_person_delay(current_signal_timing, adjusted_arrival_time, avg_arrivals=avg_arrivals),
        'detailed_timing': generate_detailed_timing_plan(current_signal_timing, optimization_horizon)
    }
    tsp_plans.append(baseline_plan)
    
    # Get the current phase, remaining time, and status based on arrival time
    phase_info = find_bus_phase(adjusted_arrival_time, current_signal_timing)
    
    # Skip if arrival time is outside the cycle
    if isinstance(phase_info, str):
        return tsp_plans
        
    phase_name, remaining_time, status = phase_info
    
    # For each possible insertion point in the cycle
    for insertion_second in range(min(int(cycle_length), optimization_horizon)):
        # Determine which phase contains this second
        insertion_phase_info = find_insertion_phase(insertion_second, current_signal_timing)
        
        if insertion_phase_info is None:
            continue
        
        insertion_phase_index, time_within_phase = insertion_phase_info
        
        # Create a copy of the current signal timing plan
        modified_plan = [phase.copy() for phase in current_signal_timing]
        
        # Determine if we need dynamic extension (5 or 7 seconds)
        dynamic_extension = determine_dynamic_extension(
            modified_plan,
            insertion_phase_index,
            phase_name,
            status,
            avg_arrivals
        )
        
        # Apply TSP at this insertion point
        tsp_modified_plan = apply_tsp_at_time(
            modified_plan, 
            insertion_phase_index, 
            time_within_phase, 
            dynamic_extension
        )
        
        # Calculate performance metrics for this plan
        bus_delay = calculate_bus_delay(tsp_modified_plan, adjusted_arrival_time)
        person_delay = calculate_person_delay(tsp_modified_plan, adjusted_arrival_time, avg_arrivals=avg_arrivals)
        
        # Generate detailed timing plan
        detailed_timing = generate_detailed_timing_plan(tsp_modified_plan, optimization_horizon)
        
        # Add this plan to our list
        tsp_plans.append({
            'plan': tsp_modified_plan,
            'type': "TSP Insertion",
            'insertion_point': insertion_second,
            'extension': dynamic_extension,
            'bus_delay': bus_delay,
            'person_delay': person_delay,
            'detailed_timing': detailed_timing
        })
    
    # Sort plans by bus delay (primary) and person delay (secondary)
    tsp_plans.sort(key=lambda x: (
        float('inf') if x['bus_delay'] is None else x['bus_delay'],
        float('inf') if x['person_delay'] is None else x['person_delay']
    ))
    
    return tsp_plans

def determine_dynamic_extension(timing_plan, phase_index, bus_phase, status, avg_arrivals):
    """
    Determine whether to use 5 or 7 seconds for TSP extension based on conditions.
    
    Parameters:
    timing_plan (list): Signal timing plan.
    phase_index (int): Index of the insertion phase.
    bus_phase (str): The phase name where the bus will arrive.
    status (str): The phase status (Green, Yellow, Red).
    avg_arrivals (dict): Average vehicle arrivals per second.
    
    Returns:
    int: 5 or 7 seconds for TSP extension.
    """
    # Default extension is 5 seconds
    extension = 5
    
    # Check if we need a 7-second extension
    # Condition: Red phase AND more than 3 vehicles in queue
    if 'North-South' not in bus_phase or status == 'Red Clearance' or 'Yellow' in bus_phase:
        # Calculate queue length for North-South direction
        queue_length = estimate_queue_length(timing_plan, 'north_south', avg_arrivals)
        
        # If more than 3 vehicles are waiting, use 7-second extension
        if queue_length > 3:
            extension = 7
    
    return extension

def estimate_queue_length(timing_plan, direction, avg_arrivals):
    """
    Estimate the number of vehicles in queue for a specific direction.
    
    Parameters:
    timing_plan (list): Signal timing plan.
    direction (str): Traffic direction ('north_south' or 'east_west').
    avg_arrivals (dict): Average vehicle arrivals per second.
    
    Returns:
    float: Estimated number of vehicles in queue.
    """
    # Get cycle length
    cycle_length = sum(phase['duration'] for phase in timing_plan)
    
    # Calculate red time for the direction
    if direction == 'north_south':
        red_time = sum(phase['duration'] for phase in timing_plan 
                       if "North-South" not in phase['phase'] or 
                       "Yellow" in phase['phase'] or 
                       "Red Clearance" in phase['phase'])
    else:  # east_west
        red_time = sum(phase['duration'] for phase in timing_plan 
                       if "East-West" not in phase['phase'] or 
                       "Yellow" in phase['phase'] or 
                       "Red Clearance" in phase['phase'])
    
    # Estimate queue based on average arrivals during red time
    queue_length = red_time * avg_arrivals[direction]
    
    return queue_length

def get_current_phase(current_time, signal_timing):
    """
    Determine the current phase and elapsed time within that phase based on current time.
    
    Parameters:
    current_time (float): Current simulation time in seconds.
    signal_timing (list): A list of dictionaries representing the signal timing plan.
    
    Returns:
    tuple or None: A tuple containing the phase index and time elapsed in phase,
                  or None if current_time is outside the cycle.
    """
    cycle_length = sum(phase['duration'] for phase in signal_timing)
    
    # Normalize current_time to within the cycle
    normalized_time = current_time % cycle_length
    
    # Find the current phase
    cumulative_time = 0
    for i, phase in enumerate(signal_timing):
        phase_end = cumulative_time + phase['duration']
        if cumulative_time <= normalized_time < phase_end:
            time_elapsed = normalized_time - cumulative_time
            return (i, time_elapsed)
        cumulative_time = phase_end
    
    return None

def create_signal_plan_from_current_time(signal_timing, current_phase_index, time_elapsed_in_phase, horizon):
    """
    Create a signal timing plan starting from the current time and extending to the specified horizon.
    
    Parameters:
    signal_timing (list): Original signal timing plan.
    current_phase_index (int): Index of current phase.
    time_elapsed_in_phase (float): Time elapsed in current phase.
    horizon (int): Time horizon for the new plan in seconds.
    
    Returns:
    list: Modified signal timing plan starting from current time.
    """
    new_plan = []
    
    # Add the current phase with remaining time
    current_phase = signal_timing[current_phase_index].copy()
    remaining_time = current_phase['duration'] - time_elapsed_in_phase
    current_phase['duration'] = remaining_time
    new_plan.append(current_phase)
    
    # Add subsequent phases until we reach the horizon
    total_time = remaining_time
    phase_index = (current_phase_index + 1) % len(signal_timing)
    
    while total_time < horizon:
        next_phase = signal_timing[phase_index].copy()
        new_plan.append(next_phase)
        total_time += next_phase['duration']
        phase_index = (phase_index + 1) % len(signal_timing)
    
    return new_plan

def generate_detailed_timing_plan(signal_timing, horizon):
    """
    Generate a detailed second-by-second signal timing plan.
    
    Parameters:
    signal_timing (list): Signal timing plan.
    horizon (int): Time horizon in seconds.
    
    Returns:
    dict: Detailed timing plan with second-by-second phase information.
    """
    detailed_plan = {
        'seconds': [],
        'north_south': [],
        'east_west': []
    }
    
    # Generate second-by-second phase information
    current_second = 0
    cumulative_time = 0
    
    for phase in signal_timing:
        phase_duration = phase['duration']
        phase_end = cumulative_time + phase_duration
        
        # Determine phase status for each direction
        ns_status = "RED"
        ew_status = "RED"
        
        if "North-South" in phase['phase']:
            if "Yellow" in phase['phase']:
                ns_status = "YELLOW"
            elif "Red Clearance" in phase['phase']:
                ns_status = "RED"
            else:
                ns_status = "GREEN"
        elif "East-West" in phase['phase']:
            if "Yellow" in phase['phase']:
                ew_status = "YELLOW"
            elif "Red Clearance" in phase['phase']:
                ew_status = "RED"
            else:
                ew_status = "GREEN"
        
        # Add each second in this phase to the detailed plan
        while cumulative_time < phase_end and current_second < horizon:
            detailed_plan['seconds'].append(current_second)
            detailed_plan['north_south'].append(ns_status)
            detailed_plan['east_west'].append(ew_status)
            
            current_second += 1
            cumulative_time += 1
        
        if current_second >= horizon:
            break
    
    return detailed_plan

def find_bus_phase(arrival_time, signal_timing):
    """
    Determine which phase the bus will arrive at based on its arrival time,
    how many seconds are left in the phase when the bus arrives, and the phase status.

    Parameters:
    arrival_time (float): The arrival time of the bus in seconds.
    signal_timing (list): A list of dictionaries representing the signal timing plan.
    
    Returns:
    tuple or str: A tuple containing the phase name, seconds left in the phase, and the phase status,
                 or a string indicating the arrival time is outside the cycle.
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

def find_insertion_phase(insertion_second, signal_timing):
    """
    Determine which phase contains the specified insertion second.
    
    Parameters:
    insertion_second (int): The second in the cycle to insert TSP.
    signal_timing (list): A list of dictionaries representing the signal timing plan.
    
    Returns:
    tuple or None: A tuple containing the phase index and the time within the phase,
                  or None if the insertion second is outside the cycle.
    """
    cumulative_time = 0
    
    for i, phase in enumerate(signal_timing):
        if cumulative_time <= insertion_second < cumulative_time + phase['duration']:
            time_within_phase = insertion_second - cumulative_time
            return (i, time_within_phase)
        cumulative_time += phase['duration']
    
    return None

def apply_tsp_at_time(signal_plan, phase_index, time_in_phase, extension):
    """
    Apply TSP by inserting a TSP green phase at the specified time point.
    
    Parameters:
    signal_plan (list): Signal timing plan.
    phase_index (int): Index of the phase containing the insertion point.
    time_in_phase (int): Time within the phase for TSP insertion.
    extension (int): Duration of TSP extension.
    
    Returns:
    list: Modified signal plan with TSP applied.
    """
    modified_plan = [phase.copy() for phase in signal_plan]
    
    # Determine the bus direction (assuming North-South direction for buses)
    bus_direction = "North-South"
    
    # Find competing direction phases to reduce time from
    competing_indices = []
    for i, phase in enumerate(modified_plan):
        if "East-West" in phase['phase'] and "Yellow" not in phase['phase'] and "Red Clearance" not in phase['phase']:
            competing_indices.append(i)
    
    # Split current phase at time_in_phase
    current_duration = modified_plan[phase_index]['duration']
    modified_plan[phase_index]['duration'] = time_in_phase
    
    # Create a TSP green phase for bus direction
    tsp_phase = {
        'phase': f"{bus_direction} TSP Green", 
        'duration': extension
    }
    
    # Create the remainder of the original phase
    remainder_phase = modified_plan[phase_index].copy()
    remainder_phase['duration'] = current_duration - time_in_phase
    
    # Insert the TSP phase and remainder
    modified_plan.insert(phase_index + 1, tsp_phase)
    modified_plan.insert(phase_index + 2, remainder_phase)
    
    # Reduce time from competing direction to maintain cycle length
    total_cycle_time = sum(phase['duration'] for phase in modified_plan)
    original_cycle_time = sum(phase['duration'] for phase in signal_plan)
    time_to_remove = total_cycle_time - original_cycle_time
    
    if competing_indices and time_to_remove > 0:
        reduction_per_phase = time_to_remove / len(competing_indices)
        for idx in competing_indices:
            # Need to adjust indices for the newly inserted phases
            adjusted_idx = idx
            if idx > phase_index:
                adjusted_idx += 2
            
            # Ensure minimum green time is maintained
            if modified_plan[adjusted_idx]['duration'] - reduction_per_phase >= 5:  # Minimum green time
                modified_plan[adjusted_idx]['duration'] -= reduction_per_phase
    
    return modified_plan

def calculate_bus_delay(timing_plan, bus_arrival_time, bus_speed=40, stop_distance=750):
    """
    Calculate the delay a bus would experience with the given timing plan.
    
    Parameters:
    timing_plan (list): Signal timing plan.
    bus_arrival_time (int): Time of bus arrival at the detection point.
    bus_speed (float): Speed of the bus in ft/s.
    stop_distance (float): Distance from detection point to the intersection.
    
    Returns:
    float: Estimated delay for the bus.
    """
    # Calculate time it takes for bus to reach intersection
    travel_time = stop_distance / bus_speed
    
    # Time when bus would arrive at intersection
    intersection_arrival_time = bus_arrival_time + travel_time
    
    # Determine what phase the bus would encounter
    cumulative_time = 0
    for phase in timing_plan:
        phase_end = cumulative_time + phase['duration']
        
        # If bus arrives during this phase
        if cumulative_time <= intersection_arrival_time < phase_end:
            # If it's a green phase for the bus direction (North-South)
            if "North-South" in phase['phase'] and "Yellow" not in phase['phase'] and "Red Clearance" not in phase['phase']:
                return 0  # No delay
            else:
                # Find next green phase for bus
                next_green_start = None
                temp_time = phase_end
                
                # Continue searching through the current cycle
                for next_phase in timing_plan[timing_plan.index(phase) + 1:]:
                    if "North-South" in next_phase['phase'] and "Yellow" not in next_phase['phase'] and "Red Clearance" not in next_phase['phase']:
                        next_green_start = temp_time
                        break
                    temp_time += next_phase['duration']
                
                # If we didn't find it, loop to the beginning of the cycle
                if next_green_start is None:
                    temp_time = 0
                    for next_phase in timing_plan[:timing_plan.index(phase)]:
                        if "North-South" in next_phase['phase'] and "Yellow" not in next_phase['phase'] and "Red Clearance" not in next_phase['phase']:
                            next_green_start = temp_time
                            break
                        temp_time += next_phase['duration']
                
                if next_green_start is None:
                    return 0  # This shouldn't happen in a properly formatted signal plan
                
                return next_green_start - intersection_arrival_time
        
        cumulative_time = phase_end
    
    return 0  # Default case

def calculate_person_delay(timing_plan, bus_arrival_time, passengers_per_bus=30, cars_per_cycle=40, passengers_per_car=1.5, avg_arrivals=None):
    """
    Calculate the person delay for all traffic users with the given timing plan.
    
    Parameters:
    timing_plan (list): Signal timing plan.
    bus_arrival_time (int): Time of bus arrival at the detection point.
    passengers_per_bus (int): Average number of passengers on the bus.
    cars_per_cycle (int): Average number of cars per cycle.
    passengers_per_car (float): Average number of passengers per car.
    avg_arrivals (dict): Average vehicle arrivals per second.
    
    Returns:
    float: Estimated person delay.
    """
    # Set default average arrivals if not provided
    if avg_arrivals is None:
        avg_arrivals = {
            'north_south': 0.3,  # vehicles per second
            'east_west': 0.25    # vehicles per second
        }
    
    # First calculate bus delay and multiply by number of passengers
    bus_delay = calculate_bus_delay(timing_plan, bus_arrival_time)
    total_bus_passenger_delay = bus_delay * passengers_per_bus
    
    # Calculate person delay over two complete cycles
    cycle_length = sum(phase['duration'] for phase in timing_plan)
    two_cycles = min(cycle_length * 2, 200)  # Cap at 200 seconds
    
    # Calculate queue lengths and delays for both directions
    ns_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'north_south', avg_arrivals, two_cycles)
    ew_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'east_west', avg_arrivals, two_cycles)
    
    # Convert vehicle delay to person delay
    ns_person_delay = ns_vehicle_delay * passengers_per_car
    ew_person_delay = ew_vehicle_delay * passengers_per_car
    
    # Total person delay
    total_person_delay = total_bus_passenger_delay + ns_person_delay + ew_person_delay
    
    return total_person_delay

def calculate_vehicle_queue_delay(timing_plan, direction, avg_arrivals, horizon):
    """
    Calculate the total delay for vehicles in a queue over the specified horizon.
    
    Parameters:
    timing_plan (list): Signal timing plan.
    direction (str): Traffic direction ('north_south' or 'east_west').
    avg_arrivals (dict): Average vehicle arrivals per second.
    horizon (int): Time horizon in seconds.
    
    Returns:
    float: Total vehicle delay in vehicle-seconds.
    """
    # Get detailed timing plan
    detailed_plan = generate_detailed_timing_plan(timing_plan, horizon)
    
    # Track queue length and total delay
    queue = 0
    total_delay = 0
    arrival_rate = avg_arrivals[direction]
    
    # Constants for queue dissipation
    saturation_flow = 1.0  # vehicles per second during green
    startup_lost_time = 2  # seconds
    
    for i in range(len(detailed_plan['seconds'])):
        # Check signal status for this direction
        if direction == 'north_south':
            status = detailed_plan['north_south'][i]
        else:
            status = detailed_plan['east_west'][i]
        
        # Add new arrivals to queue
        new_arrivals = arrival_rate
        queue += new_arrivals
        
        # Process departures during green
        if status == "GREEN":
            # Account for startup lost time
            if i > 0 and (direction == 'north_south' and detailed_plan['north_south'][i-1] != "GREEN" or
                          direction == 'east_west' and detailed_plan['east_west'][i-1] != "GREEN"):
                departure_rate = 0  # No departures during first startup_lost_time seconds
            else:
                departure_rate = saturation_flow
            
            # Vehicles leaving the queue
            departures = min(queue, departure_rate)
            queue -= departures
        
        # Add delay for all vehicles in queue during this second
        total_delay += queue
    
    return total_delay

def check_tsp_need(phase, remaining_time):
    """
    Determine if TSP is needed based on the phase and remaining time.

    Parameters:
    phase (str): The phase name.
    remaining_time (float): The remaining time in the phase when the bus arrives.

    Returns:
    str: A message indicating if TSP is needed.
    """
    if 'North-South Through' in phase and 'Yellow' not in phase and 'Red Clearance' not in phase:
        return "Bus arrives during green, no adjustments needed"
    elif 'North-South Through Yellow' in phase:
        return "Green Extension TSP is needed"
    else:
        return "Red TSP strategy is needed."

if __name__ == "__main__":
    # Use your existing signal timing plan
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
    
    # Average arrivals per second for each direction
    avg_arrivals = {
        'north_south': 0.3,  # vehicles per second
        'east_west': 0.25    # vehicles per second
    }
    
    # Current simulation time
    current_time = 40  # seconds into the simulation
    
    # Fixed bus arrival time for the exhaustive search (absolute time)
    arrival_time = 85  # This is the absolute arrival time
    
    # Get details about when the bus will arrive at the intersection
    phase_info = find_bus_phase(arrival_time - current_time, 
                               create_signal_plan_from_current_time(
                                   signal_timing, 
                                   *get_current_phase(current_time, signal_timing), 
                                   200))
    
    if not isinstance(phase_info, str):
        phase_name, remaining_time, status = phase_info
        print(f"Current simulation time: {current_time} seconds")
        print(f"The bus will arrive at the {phase_name} phase with {remaining_time} seconds left ({status}).")
        
        # Check if TSP is needed
        tsp_message = check_tsp_need(phase_name, remaining_time)
        print(tsp_message)
    
    # Run the exhaustive search
    tsp_plans = exhaustive_search_tsp(
        signal_timing, 
        arrival_time, 
        current_time=current_time, 
        max_extension=5, 
        optimization_horizon=200,
        avg_arrivals=avg_arrivals
    )
    
    # Display the results
    print("\nExhaustive TSP Search Results:")
    print("=" * 80)
    
    # Display baseline (no TSP) plan
    baseline = next(plan for plan in tsp_plans if plan['type'] == 'No TSP')
    print("\nBaseline (No TSP):")
    print(f"Bus delay: {baseline['bus_delay']:.1f} seconds")
    print(f"Person delay: {baseline['person_delay']:.1f} seconds")
    
    # Save the detailed timing plan to a file
    import json
    with open('baseline_timing_plan.json', 'w') as f:
        json.dump(baseline['detailed_timing'], f, indent=2)
    print(f"Baseline timing plan saved to 'baseline_timing_plan.json'")
    
    # Display top 5 plans
    print("\nTop 5 TSP plans by bus delay:")
    for i, plan in enumerate(tsp_plans[:6]):
        if i == 0 and plan['type'] == 'No TSP':
            # Skip the baseline plan in the top 5 if it's already the best
            continue
            
        print("\n" + "-" * 80)
        print(f"Plan {i+1}:")
        print(f"Type: {plan['type']}")
        
        if plan['insertion_point'] is not None:
            # Find which phase the insertion point is in
            insertion_phase_info = find_insertion_phase(plan['insertion_point'], signal_timing)
            if insertion_phase_info:
                insertion_phase_index, time_within_phase = insertion_phase_info
                insertion_phase = signal_timing[insertion_phase_index]['phase']
                print(f"TSP inserted during: {insertion_phase}")
                print(f"Insertion at second: {plan['insertion_point']} (within phase: {time_within_phase:.1f}s)")
        
        print(f"Extension: {plan['extension']} seconds")
        print(f"Bus delay: {plan['bus_delay']:.1f} seconds")
        print(f"Person delay: {plan['person_delay']:.1f} seconds")
        
        # Calculate improvement percentages
        if baseline['bus_delay'] > 0:
            bus_improvement = (baseline['bus_delay'] - plan['bus_delay']) / baseline['bus_delay'] * 100
            print(f"Bus delay improvement: {bus_improvement:.1f}%")
        
        if baseline['person_delay'] > 0:
            person_improvement = (baseline['person_delay'] - plan['person_delay']) / baseline['person_delay'] * 100
            print(f"Person delay improvement: {person_improvement:.1f}%")
        
        # Save the detailed timing plan to a file
        with open(f'tsp_plan_{i+1}_timing.json', 'w') as f:
            json.dump(plan['detailed_timing'], f, indent=2)
        print(f"Timing plan saved to 'tsp_plan_{i+1}_timing.json'")
    
    # Find and display the best plan that minimizes person delay
    min_person_delay = min(plan['person_delay'] for plan in tsp_plans if plan['person_delay'] is not None)
    best_person_plan = next(plan for plan in tsp_plans if plan['person_delay'] == min_person_delay)
    
    print("\n" + "=" * 80)
    print("Best plan for minimizing total person delay:")
    print(f"Type: {best_person_plan['type']}")
    
    if best_person_plan['insertion_point'] is not None:
        # Find which phase the insertion point is in
        insertion_phase_info = find_insertion_phase(best_person_plan['insertion_point'], signal_timing)
        if insertion_phase_info:
            insertion_phase_index, time_within_phase = insertion_phase_info
            insertion_phase = signal_timing[insertion_phase_index]['phase']
            print(f"TSP inserted during: {insertion_phase}")
            print(f"Insertion at second: {best_person_plan['insertion_point']} (within phase: {time_within_phase:.1f}s)")
    
    print(f"Extension: {best_person_plan['extension']} seconds")
    print(f"Bus delay: {best_person_plan['bus_delay']:.1f} seconds")
    print(f"Person delay: {best_person_plan['person_delay']:.1f} seconds")
    
    # Calculate improvement percentages
    if baseline['bus_delay'] > 0 and best_person_plan['bus_delay'] is not None:
        bus_improvement = (baseline['bus_delay'] - best_person_plan['bus_delay']) / baseline['bus_delay'] * 100
        print(f"Bus delay improvement: {bus_improvement:.1f}%")
    
    if baseline['person_delay'] > 0:
        person_improvement = (baseline['person_delay'] - best_person_plan['person_delay']) / baseline['person_delay'] * 100
        print(f"Person delay improvement: {person_improvement:.1f}%")
    
    # Save the best person plan to a file
    with open('best_person_plan_timing.json', 'w') as f:
        json.dump(best_person_plan['detailed_timing'], f, indent=2)
    print(f"Best person plan saved to 'best_person_plan_timing.json'")