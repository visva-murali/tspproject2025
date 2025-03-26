def exhaustive_search_tsp(signal_timing, max_extension=5):
    """
    Perform an exhaustive search that tests applying TSP at every possible second
    of the traffic signal cycle to find optimal timing plans.
    
    Parameters:
    signal_timing (list): A list of dictionaries representing the signal timing plan.
    max_extension (int): The maximum extension for TSP (in seconds).
    
    Returns:
    list: A list of modified signal timing plans with performance metrics.
    """
    # Calculate total cycle length
    cycle_length = sum(phase['duration'] for phase in signal_timing)
    
    # List to store all possible TSP timing plans
    tsp_plans = []
    
    # First, add a baseline "no TSP" plan
    baseline_plan = {
        'plan': signal_timing.copy(),
        'type': 'No TSP',
        'bus_arrival_time': None,
        'insertion_point': None,
        'extension': None,
        'bus_delay': None,
        'person_delay': None
    }
    tsp_plans.append(baseline_plan)
    
    # For each possible bus arrival time in the cycle
    for arrival_time in range(int(cycle_length)):
        # Get the current phase, remaining time, and status based on arrival time
        phase_info = find_bus_phase(arrival_time, signal_timing)
        
        # Skip if arrival time is outside the cycle
        if isinstance(phase_info, str):
            continue
            
        phase_name, remaining_time, status = phase_info
        
        # Create a copy of the original signal timing plan
        modified_plan = [phase.copy() for phase in signal_timing]
        
        # Determine which TSP strategy to use based on the phase
        tsp_strategy = check_tsp_need(phase_name, remaining_time)
        
        # Apply the appropriate TSP strategy
        if tsp_strategy == "Bus arrives during green, no adjustments needed":
            # No TSP needed
            tsp_modified_plan = modified_plan
            tsp_type = "No TSP Needed"
            extension = 0
        elif tsp_strategy == "Green Extension TSP is needed":
            # Apply green extension
            tsp_modified_plan = apply_green_extension(modified_plan, phase_name, max_extension)
            tsp_type = "Green Extension"
            extension = max_extension
        else:  # "Red TSP strategy is needed"
            # For each possible insertion point in the cycle
            for insertion_second in range(int(cycle_length)):
                # Determine which phase contains this second
                insertion_phase_info = find_insertion_phase(insertion_second, signal_timing)
                
                if insertion_phase_info is None:
                    continue
                
                insertion_phase_index, time_within_phase = insertion_phase_info
                
                # Apply TSP at this insertion point
                tsp_modified_plan = apply_tsp_at_time(
                    modified_plan.copy(), 
                    insertion_phase_index, 
                    time_within_phase, 
                    max_extension
                )
                
                # Calculate performance metrics for this plan
                bus_delay = calculate_bus_delay(tsp_modified_plan, arrival_time)
                person_delay = calculate_person_delay(tsp_modified_plan, arrival_time)
                
                # Add this plan to our list
                tsp_plans.append({
                    'plan': tsp_modified_plan,
                    'type': "Red TSP",
                    'bus_arrival_time': arrival_time,
                    'insertion_point': insertion_second,
                    'extension': max_extension,
                    'bus_delay': bus_delay,
                    'person_delay': person_delay
                })
            
            # Skip the rest of this iteration since we've already added all insertion plans
            continue
        
        # Calculate performance metrics for green extension or no TSP plans
        bus_delay = calculate_bus_delay(tsp_modified_plan, arrival_time)
        person_delay = calculate_person_delay(tsp_modified_plan, arrival_time)
        
        # Add this plan to our list
        tsp_plans.append({
            'plan': tsp_modified_plan,
            'type': tsp_type,
            'bus_arrival_time': arrival_time,
            'insertion_point': None,  # For green extension, there's no insertion point
            'extension': extension,
            'bus_delay': bus_delay,
            'person_delay': person_delay
        })
    
    # Sort plans by bus delay (primary) and person delay (secondary)
    tsp_plans.sort(key=lambda x: (
        float('inf') if x['bus_delay'] is None else x['bus_delay'],
        float('inf') if x['person_delay'] is None else x['person_delay']
    ))
    
    return tsp_plans

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

def apply_green_extension(signal_plan, phase_name, extension):
    """
    Apply green extension TSP strategy.
    
    Parameters:
    signal_plan (list): Signal timing plan.
    phase_name (str): The name of the phase to extend.
    extension (int): Duration of TSP extension.
    
    Returns:
    list: Modified signal plan with green extension applied.
    """
    modified_plan = [phase.copy() for phase in signal_plan]
    
    # Find the phase to extend
    ns_through_index = next((i for i, phase in enumerate(modified_plan) 
                           if phase['phase'] == 'North-South Through'), None)
    
    # Find a competing phase to reduce time from
    ew_through_index = next((i for i, phase in enumerate(modified_plan) 
                           if phase['phase'] == 'East-West Through'), None)
    
    if ns_through_index is not None and ew_through_index is not None:
        # Extend the North-South Through phase
        modified_plan[ns_through_index]['duration'] += extension
        
        # Reduce time from the East-West Through phase to maintain cycle length
        if modified_plan[ew_through_index]['duration'] - extension >= 5:  # Minimum green time
            modified_plan[ew_through_index]['duration'] -= extension
    
    return modified_plan

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


def calculate_person_delay(timing_plan, bus_arrival_time, passengers_per_bus=30, cars_per_cycle=40, passengers_per_car=1.5):
    """
    Calculate the person delay for all traffic users with the given timing plan.
    
    Parameters:
    timing_plan (list): Signal timing plan.
    bus_arrival_time (int): Time of bus arrival at the detection point.
    passengers_per_bus (int): Average number of passengers on the bus.
    cars_per_cycle (int): Average number of cars per cycle.
    passengers_per_car (float): Average number of passengers per car.
    
    Returns:
    float: Estimated person delay.
    """
    # First calculate bus delay and multiply by number of passengers
    bus_delay = calculate_bus_delay(timing_plan, bus_arrival_time)
    total_bus_passenger_delay = bus_delay * passengers_per_bus
    
    # Calculate average delay for cars based on the timing plan
    cycle_length = sum(phase['duration'] for phase in timing_plan)
    
    # Calculate green time for each direction
    ns_green_time = sum(phase['duration'] for phase in timing_plan 
                         if "North-South" in phase['phase'] and 
                         "Yellow" not in phase['phase'] and 
                         "Red Clearance" not in phase['phase'])
    
    ew_green_time = sum(phase['duration'] for phase in timing_plan 
                         if "East-West" in phase['phase'] and 
                         "Yellow" not in phase['phase'] and 
                         "Red Clearance" not in phase['phase'])
    
    # Calculate delay for cars in each direction
    # Assume car distribution is proportional to green time allocation
    ns_car_ratio = ns_green_time / (ns_green_time + ew_green_time)
    ew_car_ratio = ew_green_time / (ns_green_time + ew_green_time)
    
    ns_cars = cars_per_cycle * ns_car_ratio
    ew_cars = cars_per_cycle * ew_car_ratio
    
    # Estimate average delay for cars (half of red time)
    ns_avg_delay = (cycle_length - ns_green_time) / 2
    ew_avg_delay = (cycle_length - ew_green_time) / 2
    
    # Calculate total car passenger delay
    ns_car_passenger_delay = ns_cars * ns_avg_delay * passengers_per_car
    ew_car_passenger_delay = ew_cars * ew_avg_delay * passengers_per_car
    total_car_passenger_delay = ns_car_passenger_delay + ew_car_passenger_delay
    
    # Total person delay
    total_person_delay = total_bus_passenger_delay + total_car_passenger_delay
    
    return total_person_delay

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
    
    # Run the exhaustive search
    tsp_plans = exhaustive_search_tsp(signal_timing, max_extension=5)
    
    # Group plans by bus arrival time
    arrival_times = sorted(set(plan['bus_arrival_time'] for plan in tsp_plans if plan['bus_arrival_time'] is not None))
    
    # Display plans organized by bus arrival time
    print("Exhaustive TSP Search Results:")
    print("=" * 80)
    
    print("\nBaseline (No TSP):")
    baseline = next(plan for plan in tsp_plans if plan['type'] == 'No TSP')
    print(f"Person delay: {baseline['person_delay']} seconds")
    
    for arrival_time in arrival_times:
        # Find the best plan for this arrival time
        best_plan = None
        min_bus_delay = float('inf')
        
        for plan in tsp_plans:
            if plan['bus_arrival_time'] == arrival_time and plan['bus_delay'] is not None:
                if plan['bus_delay'] < min_bus_delay:
                    min_bus_delay = plan['bus_delay']
                    best_plan = plan
        
        if best_plan:
            # Get the phase information for this arrival time
            phase_info = find_bus_phase(arrival_time, signal_timing)
            if isinstance(phase_info, str):
                continue
            phase_name, remaining_time, status = phase_info
            
            print("\n" + "-" * 80)
            print(f"Bus arrival time: {arrival_time} seconds")
            print(f"Bus arrives at: {phase_name} phase with {remaining_time:.1f} seconds remaining ({status})")
            print(f"Best TSP strategy: {best_plan['type']}")
            
            if best_plan['insertion_point'] is not None:
                print(f"TSP insertion at: {best_plan['insertion_point']} seconds")
            
            print(f"Extension: {best_plan['extension']} seconds")
            print(f"Bus delay: {best_plan['bus_delay']:.1f} seconds")
            print(f"Person delay: {best_plan['person_delay']:.1f} seconds")
            
            # Calculate improvement percentages
            if baseline['bus_delay'] is not None and baseline['bus_delay'] > 0:
                bus_improvement = (baseline['bus_delay'] - best_plan['bus_delay']) / baseline['bus_delay'] * 100
                print(f"Bus delay improvement: {bus_improvement:.1f}%")
            
            if baseline['person_delay'] is not None and baseline['person_delay'] > 0:
                person_improvement = (baseline['person_delay'] - best_plan['person_delay']) / baseline['person_delay'] * 100
                print(f"Person delay improvement: {person_improvement:.1f}%")