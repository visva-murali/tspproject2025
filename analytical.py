import copy
import json
from typing import Dict, List, Optional, Tuple

MIN_GREEN = 5  # minimum green duration in seconds
YELLOW_DURATION = 4  # fixed yellow duration after every green

def validate_plan(plan: List[Dict]) -> bool:
    """
    Validate a 4-phase signal plan.
    - Exactly 4 phases.
    - Alternates Green, Yellow, Green, Yellow.
    - Green >= MIN_GREEN, Yellow == YELLOW_DURATION.
    """
    if len(plan) != 4:
        return False
    for i, phase in enumerate(plan):
        if i % 2 == 0:
            # Green phase
            if "Green" not in phase['phase'] or phase['duration'] < MIN_GREEN:
                return False
        else:
            # Yellow phase
            if "Yellow" not in phase['phase'] or abs(phase['duration'] - YELLOW_DURATION) > 0.01:
                return False
    return True

def adjust_four_phase_plan_to_cycle_length(plan: List[Dict], target_cycle_length: float) -> List[Dict]:
    """
    Adjust the green durations in a four-phase plan so that the total cycle length matches the target.
    Keeps yellow durations fixed, distributes extra/missing time proportionally to green phases.
    """
    green_indices = [i for i, p in enumerate(plan) if "Green" in p['phase']]
    yellow_indices = [i for i, p in enumerate(plan) if "Yellow" in p['phase']]
    total_green = sum(plan[i]['duration'] for i in green_indices)
    total_yellow = sum(plan[i]['duration'] for i in yellow_indices)
    current_cycle = total_green + total_yellow
    diff = target_cycle_length - current_cycle
    if abs(diff) < 1e-6:
        return plan
    # Distribute diff proportionally to green phases
    for i in green_indices:
        prop = plan[i]['duration'] / total_green if total_green > 0 else 0.5
        plan[i]['duration'] += diff * prop
        plan[i]['duration'] = max(plan[i]['duration'], MIN_GREEN)
    # Recalculate in case rounding caused drift
    total_green = sum(plan[i]['duration'] for i in green_indices)
    plan_cycle = total_green + total_yellow
    # If still off, adjust first green
    if abs(plan_cycle - target_cycle_length) > 1e-6:
        plan[green_indices[0]]['duration'] += target_cycle_length - plan_cycle
        plan[green_indices[0]]['duration'] = max(plan[green_indices[0]]['duration'], MIN_GREEN)
    return plan

def extract_four_phases(full_plan: List[Dict]) -> List[Dict]:
    """
    Extract the four core phases (NS/EW Green/Yellow) in order from a possibly expanded plan.
    Returns a list of 4 dicts: [NS Green, NS Yellow, EW Green, EW Yellow].
    """
    core_phases = []
    ns_green = next((p for p in full_plan if "North-South Through Green" in p['phase'] or (p['phase'] == "North-South Through" and "Green" in p['phase'])), None)
    ns_yellow = next((p for p in full_plan if "North-South Through Yellow" in p['phase']), None)
    ew_green = next((p for p in full_plan if "East-West Through Green" in p['phase'] or (p['phase'] == "East-West Through" and "Green" in p['phase'])), None)
    ew_yellow = next((p for p in full_plan if "East-West Through Yellow" in p['phase']), None)
    # Fallback: try to match by phase name if above fails
    if not ns_green:
        ns_green = next((p for p in full_plan if "North-South Through" in p['phase'] and "Yellow" not in p['phase']), None)
    if not ew_green:
        ew_green = next((p for p in full_plan if "East-West Through" in p['phase'] and "Yellow" not in p['phase']), None)
    if not ns_yellow:
        ns_yellow = next((p for p in full_plan if "North-South Through Yellow" in p['phase']), None)
    if not ew_yellow:
        ew_yellow = next((p for p in full_plan if "East-West Through Yellow" in p['phase']), None)
    for p in [ns_green, ns_yellow, ew_green, ew_yellow]:
        if p:
            core_phases.append({'phase': p['phase'], 'duration': p['duration']})
        else:
            core_phases.append({'phase': '', 'duration': 0})
    return core_phases

def exhaustive_search_tsp(
    signal_timing: List[Dict],
    arrival_time: float,
    current_time: float = 0,
    max_extension: int = 5,
    optimization_horizon: int = 200,
    avg_arrivals: Optional[Dict] = None
) -> List[Dict]:
    """
    Perform exhaustive search for TSP insertion, returning only valid 4-phase plans.
    """
    if avg_arrivals is None:
        avg_arrivals = {
            'north left': 0.3, 'north through': 0.3, 'north right': .2,
            'south left': 0.3, 'south through': 0.3, 'south right': .2,
            'east left': 0.3, 'east through': 0.3, 'east right': .2,
            'west left': 0.3, 'west through': 0.3, 'west right': .2,
        }
    cycle_length = sum(phase['duration'] for phase in signal_timing)
    adjusted_arrival_time = arrival_time - current_time if arrival_time >= current_time else arrival_time
    current_phase_info = get_current_phase(current_time, signal_timing)
    if current_phase_info is None:
        current_phase_index, time_elapsed_in_phase = 0, 0
    else:
        current_phase_index, time_elapsed_in_phase = current_phase_info
    current_signal_timing = create_signal_plan_from_current_time(signal_timing, current_phase_index, time_elapsed_in_phase, optimization_horizon)
    tsp_plans = []
    # Baseline plan
    baseline_plan = {
        'plan': extract_four_phases(current_signal_timing),
        'type': 'No TSP',
        'insertion_point': None,
        'extension': None,
        'bus_delay': calculate_bus_delay(current_signal_timing, adjusted_arrival_time),
        'person_delay': calculate_person_delay(current_signal_timing, adjusted_arrival_time, avg_arrivals=avg_arrivals, cycle_length=cycle_length),
        'detailed_timing': generate_detailed_timing_plan(current_signal_timing, optimization_horizon, cycle_length)
    }
    baseline_plan['plan'] = adjust_four_phase_plan_to_cycle_length(baseline_plan['plan'], cycle_length)
    if validate_plan(baseline_plan['plan']):
        tsp_plans.append(baseline_plan)
    phase_info = find_bus_phase(adjusted_arrival_time, current_signal_timing)
    if isinstance(phase_info, str):
        return tsp_plans
    phase_name, remaining_time, status = phase_info
    for insertion_second in range(min(int(cycle_length), optimization_horizon)):
        insertion_phase_info = find_insertion_phase(insertion_second, current_signal_timing)
        if insertion_phase_info is None:
            continue
        insertion_phase_index, time_within_phase = insertion_phase_info
        modified_plan = [phase.copy() for phase in current_signal_timing]
        dynamic_extension = MIN_GREEN  # always use MIN_GREEN for extension in this context
        tsp_modified_plan = apply_tsp_at_time(
            modified_plan,
            insertion_phase_index,
            time_within_phase,
            dynamic_extension
        )
        if tsp_modified_plan is None:
            continue
        four_phase_plan = extract_four_phases(tsp_modified_plan)
        four_phase_plan = adjust_four_phase_plan_to_cycle_length(four_phase_plan, cycle_length)
        if not validate_plan(four_phase_plan):
            continue
        bus_delay = calculate_bus_delay(tsp_modified_plan, adjusted_arrival_time)
        person_delay = calculate_person_delay(tsp_modified_plan, adjusted_arrival_time, avg_arrivals=avg_arrivals, cycle_length=cycle_length)
        detailed_timing = generate_detailed_timing_plan(tsp_modified_plan, optimization_horizon, cycle_length)
        tsp_plans.append({
            'plan': four_phase_plan,
            'type': "TSP Insertion",
            'insertion_point': insertion_second,
            'extension': dynamic_extension,
            'bus_delay': bus_delay,
            'person_delay': person_delay,
            'detailed_timing': detailed_timing
        })
    tsp_plans = [p for p in tsp_plans if validate_plan(p['plan'])]
    tsp_plans.sort(key=lambda x: (
        float('inf') if x['bus_delay'] is None else x['bus_delay'],
        float('inf') if x['person_delay'] is None else x['person_delay']
    ))
    return tsp_plans

def apply_tsp_at_time(
    signal_plan: List[Dict],
    phase_index: int,
    time_in_phase: float,
    extension: int
) -> Optional[List[Dict]]:
    """
    Apply TSP by splitting a green phase and inserting TSP green/yellow.
    EW greens are reduced proportionally to keep cycle length, but never below MIN_GREEN.
    """
    modified_plan = [phase.copy() for phase in signal_plan]
    phase = modified_plan[phase_index]
    if "Green" not in phase['phase'] and "Through" not in phase['phase']:
        return None
    before_duration = time_in_phase
    after_duration = phase['duration'] - time_in_phase
    if (before_duration > 0 and before_duration < MIN_GREEN) or (after_duration > 0 and after_duration < MIN_GREEN):
        return None
    del modified_plan[phase_index]
    insert_at = phase_index
    if before_duration >= MIN_GREEN:
        modified_plan.insert(insert_at, {'phase': phase['phase'], 'duration': before_duration})
        insert_at += 1
    tsp_green = {'phase': "North-South Through Green", 'duration': extension}
    tsp_yellow = {'phase': "North-South Through Yellow", 'duration': YELLOW_DURATION}
    modified_plan.insert(insert_at, tsp_green)
    modified_plan.insert(insert_at + 1, tsp_yellow)
    insert_at += 2
    if after_duration >= MIN_GREEN:
        modified_plan.insert(insert_at, {'phase': phase['phase'], 'duration': after_duration})
    # Adjust EW greens proportionally to keep cycle length
    total_cycle_time = sum(p['duration'] for p in modified_plan)
    original_cycle_time = sum(p['duration'] for p in signal_plan)
    time_to_remove = total_cycle_time - original_cycle_time
    ew_green_indices = [i for i, p in enumerate(modified_plan) if "East-West Through" in p['phase'] and "Green" in p['phase']]
    if time_to_remove > 0 and ew_green_indices:
        total_ew_green = sum(modified_plan[i]['duration'] for i in ew_green_indices)
        for i in ew_green_indices:
            green = modified_plan[i]
            max_reducible = green['duration'] - MIN_GREEN
            reduction = min(time_to_remove * (green['duration'] / total_ew_green), max_reducible)
            green['duration'] -= reduction
            time_to_remove -= reduction
            if time_to_remove <= 0:
                break
        if time_to_remove > 0:
            return None
    # Enforce yellow and min green
    enforced = enforce_yellow_and_min_green(modified_plan)
    if enforced is None or not is_valid_signal_plan(enforced):
        return None
    return enforced

def generate_detailed_timing_plan(signal_timing: List[Dict], horizon: int, cycle_length: float) -> Dict:
    """
    Generate a second-by-second plan:
    {
        'seconds': [...],
        'phase': [...],
        'directions': {
            'North-South-Left': [...],
            'North-South-Through': [...],
            'East-West-Left': [...],
            'East-West-Through': [...]
        }
    }
    Each direction array contains "GREEN", "YELLOW", or "RED" for each second.
    """
    # Define which phases control which directions and their color mapping
    direction_phase_map = {
        'North-South-Left': {
            'green': ['North-South Left Green'],
            'yellow': ['North-South Left Yellow']
        },
        'North-South-Through': {
            'green': ['North-South Through Green'],
            'yellow': ['North-South Through Yellow']
        },
        'East-West-Left': {
            'green': ['East-West Left Green'],
            'yellow': ['East-West Left Yellow']
        },
        'East-West-Through': {
            'green': ['East-West Through Green'],
            'yellow': ['East-West Through Yellow']
        }
    }
    # If left phases are not present, treat through phases as controlling all
    # (for simple 4-phase plans)
    for d in direction_phase_map:
        if not any(phase['phase'] in direction_phase_map[d]['green'] for phase in signal_timing):
            if 'Through' in d:
                direction_phase_map[d]['green'] = [d.replace('-', ' ') + ' Green']
                direction_phase_map[d]['yellow'] = [d.replace('-', ' ') + ' Yellow']
            else:
                # For lefts, fallback to through
                base = d.replace('Left', 'Through')
                direction_phase_map[d]['green'] = [base.replace('-', ' ') + ' Green']
                direction_phase_map[d]['yellow'] = [base.replace('-', ' ') + ' Yellow']

    detailed = {
        'seconds': [],
        'phase': [],
        'directions': {
            'North-South-Left': [],
            'North-South-Through': [],
            'East-West-Left': [],
            'East-West-Through': []
        }
    }
    current_second = 0
    phase_idx = 0
    phase_time = 0
    while current_second < horizon:
        phase = signal_timing[phase_idx]
        phase_duration = int(round(phase['duration']))
        for t in range(phase_duration):
            if current_second >= horizon:
                break
            detailed['seconds'].append(current_second)
            detailed['phase'].append(phase['phase'])
            for direction, mapping in direction_phase_map.items():
                if phase['phase'] in mapping['green']:
                    detailed['directions'][direction].append("GREEN")
                elif phase['phase'] in mapping['yellow']:
                    detailed['directions'][direction].append("YELLOW")
                else:
                    detailed['directions'][direction].append("RED")
            current_second += 1
        phase_idx = (phase_idx + 1) % len(signal_timing)
    return detailed

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
    if 'North-South-Through' not in bus_phase or status == 'Red Clearance' or 'Yellow' in bus_phase:
        # Calculate queue length for North-South direction
        queue_length = estimate_queue_length(timing_plan, 'north through', avg_arrivals)
        
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
    if direction == 'North-South-Left':
        red_time = sum(phase['duration'] for phase in timing_plan 
                       if "North-South-Left" not in phase['phase'] or 
                       "Yellow" in phase['phase'] or 
                       "Red Clearance" in phase['phase'])
    elif direction == 'North-South-Through':
        red_time = sum(phase['duration'] for phase in timing_plan 
                       if "North-South-Through" not in phase['phase'] or 
                       "Yellow" in phase['phase'] or 
                       "Red Clearance" in phase['phase'])
    elif direction == 'East-West-Through':
        red_time = sum(phase['duration'] for phase in timing_plan 
                       if "North-South-Through" not in phase['phase'] or 
                       "Yellow" in phase['phase'] or 
                       "Red Clearance" in phase['phase'])
    else:  # east_west
        red_time = sum(phase['duration'] for phase in timing_plan 
                       if "East-West-Through" not in phase['phase'] or 
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
    intersection_arrival_time = bus_arrival_time + travel_time #this value will change based on what ridwan does
    
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

def calculate_person_delay(
    timing_plan, 
    bus_arrival_time, 
    passengers_per_bus=30, 
    cars_per_cycle=40, 
    passengers_per_car=1.5, 
    avg_arrivals=None,
    cycle_length=None
):
    """
    Calculate the person delay for all traffic users with the given timing plan.
    """
    if avg_arrivals is None:
        avg_arrivals = {
            'north left': 0.3,  # vehicles per second
            'north through': 0.3, 
            'north right': .2,
            'south left': 0.3,  # vehicles per second
            'south through': 0.3, 
            'south right': .2,
            'east left': 0.3,  # vehicles per second
            'east through': 0.3, 
            'east right': .2,
            'west left': 0.3,  # vehicles per second
            'west through': 0.3, 
            'west right': .2,      # vehicles per second
        }
    bus_delay = calculate_bus_delay(timing_plan, bus_arrival_time)
    total_bus_passenger_delay = bus_delay * passengers_per_bus
    # Calculate person delay over two complete cycles
    if cycle_length is None:
        cycle_length = sum(phase['duration'] for phase in timing_plan)
    two_cycles = min(cycle_length * 2, 200)  # Cap at 200 seconds
    north_left_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'north left', avg_arrivals, two_cycles, cycle_length)
    north_through_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'north through', avg_arrivals, two_cycles, cycle_length)
    north_right_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'north right', avg_arrivals, two_cycles, cycle_length)
    south_left_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'south left', avg_arrivals, two_cycles, cycle_length)
    south_through_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'south through', avg_arrivals, two_cycles, cycle_length)
    south_right_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'south right', avg_arrivals, two_cycles, cycle_length)
    east_left_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'east left', avg_arrivals, two_cycles, cycle_length)
    east_through_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'east through', avg_arrivals, two_cycles, cycle_length)
    east_right_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'east right', avg_arrivals, two_cycles, cycle_length)
    west_left_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'west left', avg_arrivals, two_cycles, cycle_length)
    west_through_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'west through', avg_arrivals, two_cycles, cycle_length)
    west_right_vehicle_delay = calculate_vehicle_queue_delay(timing_plan, 'west right', avg_arrivals, two_cycles, cycle_length)
    delays = [
        north_left_vehicle_delay, north_through_vehicle_delay, north_right_vehicle_delay,
        south_left_vehicle_delay, south_through_vehicle_delay, south_right_vehicle_delay,
        east_left_vehicle_delay, east_through_vehicle_delay, east_right_vehicle_delay,
        west_left_vehicle_delay, west_through_vehicle_delay, west_right_vehicle_delay
    ]
    if any(d == float('inf') for d in delays):
        return float('inf')
    nl_person_delay = north_left_vehicle_delay * passengers_per_car
    nt_person_delay = north_through_vehicle_delay * passengers_per_car
    nr_person_delay = north_right_vehicle_delay * passengers_per_car
    sl_person_delay = south_left_vehicle_delay * passengers_per_car
    st_person_delay = south_through_vehicle_delay * passengers_per_car
    sr_person_delay = south_right_vehicle_delay * passengers_per_car
    el_person_delay = east_left_vehicle_delay * passengers_per_car
    et_person_delay = east_through_vehicle_delay * passengers_per_car
    er_person_delay = east_right_vehicle_delay * passengers_per_car
    wl_person_delay = west_left_vehicle_delay * passengers_per_car
    wt_person_delay = west_through_vehicle_delay * passengers_per_car
    wr_person_delay = west_right_vehicle_delay * passengers_per_car
    total_person_delay = total_bus_passenger_delay + nl_person_delay + nt_person_delay + nr_person_delay + sl_person_delay + st_person_delay + sr_person_delay + el_person_delay + et_person_delay + er_person_delay + wt_person_delay + wl_person_delay + wr_person_delay
    return total_person_delay

def calculate_vehicle_queue_delay(timing_plan, direction, avg_arrivals, horizon, cycle_length=None):
    """
    Calculate the total delay for vehicles in a queue over the specified horizon.
    Uses correct mapping for direction and phase.
    """
    if cycle_length is None:
        cycle_length = sum(phase['duration'] for phase in timing_plan)
    detailed_plan = generate_detailed_timing_plan(timing_plan, horizon, cycle_length)
    # Defensive: If detailed_plan is empty or invalid, return a very high delay to avoid selection
    if not detailed_plan or not detailed_plan['seconds']:
        return float('inf')
    # Map direction to detailed_plan key
    dir_map = {
        'north left': 'North-South-Left',
        'north through': 'North-South-Through',
        'south left': 'North-South-Left',
        'south through': 'North-South-Through',
        'east left': 'East-West-Left',
        'east through': 'East-West-Through',
        'west left': 'East-West-Left',
        'west through': 'East-West-Through',
        'north right': 'North-South-Left',
        'south right': 'North-South-Left',
        'east right': 'East-West-Left',
        'west right': 'East-West-Left'
    }
    phase_key = dir_map[direction]
    queue = 0
    total_delay = 0
    arrival_rate = avg_arrivals[direction]
    saturation_flow = 1.0  # vehicles per second during green
    startup_lost_time = 2  # seconds
    green_streak = 0
    for i in range(len(detailed_plan['seconds'])):
        status = detailed_plan['directions'][phase_key][i]
        queue += arrival_rate
        if status == "GREEN":
            if green_streak < startup_lost_time:
                departure_rate = 0
                green_streak += 1
            else:
                departure_rate = saturation_flow
            departures = min(queue, departure_rate)
            queue -= departures
        else:
            green_streak = 0
        total_delay += queue
    return total_delay

def check_tsp_need(phase, remaining_time):
    """
    Determine if TSP is needed based on the phase and remaining time.

    Parameters:
    phase (str): The phase name.
    remaining time (float): The remaining time in the phase when the bus arrives.

    Returns:
    str: A message indicating if TSP is needed.
    """
    if 'North-South Through' in phase and 'Yellow' not in phase and 'Red Clearance' not in phase:
        return "Bus arrives during green, no adjustments needed"
    elif 'North-South Through Yellow' in phase:
        return "Green Extension TSP is needed"
    else:
        return "Red TSP strategy is needed."

def enforce_yellow_and_min_green(signal_plan: List[Dict]) -> Optional[List[Dict]]:
    """
    Ensure every green phase is followed by a 4s yellow, and all greens are at least MIN_GREEN.
    Returns a new plan or None if constraints are violated.
    """
    new_plan = []
    i = 0
    while i < len(signal_plan):
        phase = signal_plan[i]
        if "Green" in phase['phase']:
            if phase['duration'] < MIN_GREEN:
                return None
            new_plan.append({'phase': phase['phase'], 'duration': phase['duration']})
            yellow_phase = phase['phase'].replace("Green", "Yellow")
            new_plan.append({'phase': yellow_phase, 'duration': YELLOW_DURATION})
            if i+1 < len(signal_plan) and "Yellow" in signal_plan[i+1]['phase']:
                i += 1
        elif "Yellow" in phase['phase']:
            pass
        else:
            new_plan.append({'phase': phase['phase'], 'duration': phase['duration']})
        i += 1
    if not any("Green" in p['phase'] for p in new_plan):
        return None
    return new_plan

def is_valid_signal_plan(signal_plan: List[Dict]) -> bool:
    """
    Returns True if all green phases are >=MIN_GREEN and every green is followed by a yellow (YELLOW_DURATION).
    """
    has_green = False
    for i, phase in enumerate(signal_plan):
        if "Green" in phase['phase']:
            has_green = True
            if phase['duration'] < MIN_GREEN:
                return False
            if i+1 >= len(signal_plan):
                return False
            expected_yellow = phase['phase'].replace("Green", "Yellow")
            if signal_plan[i+1]['phase'] != expected_yellow or abs(signal_plan[i+1]['duration'] - YELLOW_DURATION) > 0.01:
                return False
    return has_green

def track_vehicle_queue(signal_timing, direction, avg_arrivals, horizon=200, cycle_length=None):
    """
    Track the queue length for a given direction over the specified horizon.
    Returns a list of queue lengths per second.
    """
    if cycle_length is None:
        cycle_length = sum(phase['duration'] for phase in signal_timing)
    detailed_plan = generate_detailed_timing_plan(signal_timing, horizon, cycle_length)
    dir_map = {
        'north left': 'North-South-Left',
        'north through': 'North-South-Through',
        'south left': 'North-South-Left',
        'south through': 'North-South-Through',
        'east left': 'East-West-Left',
        'east through': 'East-West-Through',
        'west left': 'East-West-Left',
        'west through': 'East-West-Through',
        'north right': 'North-South-Left',
        'south right': 'North-South-Left',
        'east right': 'East-West-Left',
        'west right': 'East-West-Left'
    }
    phase_key = dir_map[direction]
    queue_lengths = []
    queue = 0
    arrival_rate = avg_arrivals[direction]
    saturation_flow = 1.0  # vehicles per second during green
    startup_lost_time = 2  # seconds
    green_streak = 0
    for i in range(len(detailed_plan['seconds'])):
        status = detailed_plan['directions'][phase_key][i]
        queue += arrival_rate
        if status == "GREEN":
            if green_streak < startup_lost_time:
                departure_rate = 0
                green_streak += 1
            else:
                departure_rate = saturation_flow
            departures = min(queue, departure_rate)
            queue -= departures
        else:
            green_streak = 0
        queue_lengths.append(queue)
    return queue_lengths

def is_detailed_plan_all_red(detailed_plan):
    """
    Returns True if all directions are RED for all seconds in the detailed plan.
    Returns True if the plan is None or empty (since we can't use a plan with no signals).
    """
    if detailed_plan is None or not isinstance(detailed_plan, dict) or 'seconds' not in detailed_plan or not detailed_plan['seconds']:
        return True
    for sec in range(len(detailed_plan['seconds'])):
        if (detailed_plan['directions']['North-South-Left'][sec] == "GREEN" or
            detailed_plan['directions']['North-South-Through'][sec] == "GREEN" or
            detailed_plan['directions']['East-West-Left'][sec] == "GREEN" or
            detailed_plan['directions']['East-West-Through'][sec] == "GREEN"):
            return False
    return True

if __name__ == "__main__":
    # Sample 4-phase plan: NS Green/Yellow, EW Green/Yellow
    # User can set cycle_length here (e.g., 100s)
    cycle_length = 100
    # Distribute green times to match cycle length
    base_greens = [30, 30]
    base_yellows = [YELLOW_DURATION, YELLOW_DURATION]
    total_base = sum(base_greens) + sum(base_yellows)
    extra = cycle_length - total_base
    # Distribute extra time proportionally to greens
    greens = [g + extra * (g / sum(base_greens)) for g in base_greens]
    signal_timing = [
        {'phase': 'North-South Through Green', 'duration': greens[0]},
        {'phase': 'North-South Through Yellow', 'duration': YELLOW_DURATION},
        {'phase': 'East-West Through Green', 'duration': greens[1]},
        {'phase': 'East-West Through Yellow', 'duration': YELLOW_DURATION},
    ]
    avg_arrivals = {
        'north left': 0.3, 'north through': 0.3, 'north right': .2,
        'south left': 0.3, 'south through': 0.3, 'south right': .2,
        'east left': 0.3, 'east through': 0.3, 'east right': .2,
        'west left': 0.3, 'west through': 0.3, 'west right': .2,
    }
    arrival_time = 20
    horizon = int(min(2 * cycle_length, 200))  # 2 cycles, capped at 200s

    tsp_plans = exhaustive_search_tsp(
        signal_timing,
        arrival_time,
        current_time=0,
        max_extension=MIN_GREEN,
        optimization_horizon=horizon,
        avg_arrivals=avg_arrivals
    )
    print("\nTop 10 valid TSP plans (bus_delay, person_delay):")
    # Only output as many plans as exist, up to 10
    num_plans = min(10, len(tsp_plans))
    for i in range(num_plans):
        plan = tsp_plans[i]
        print(f"Plan {i+1}: Bus delay={plan['bus_delay']:.2f}, Person delay={plan['person_delay']:.2f}")
        output_json = {
            "summary": {
                "bus_delay": plan['bus_delay'],
                "person_delay": plan['person_delay'],
                "insertion_point": plan['insertion_point'],
                "extension": plan['extension'],
                "type": plan['type']
            },
            "four_phase_plan": [
                {
                    "phase": p["phase"],
                    "duration": p["duration"]
                } for p in plan["plan"]
            ],
            "detailed_timing": plan["detailed_timing"]
        }
        with open(f"tsp_plan_{i+1}_timing.json", "w") as f:
            json.dump(output_json, f, indent=2)
    # For any remaining files up to 10, write a placeholder but do NOT overwrite existing valid plans
    for i in range(num_plans, 10):
        output_json = {
            "summary": {
                "bus_delay": None,
                "person_delay": None,
                "insertion_point": None,
                "extension": None,
                "type": None
            },
            "four_phase_plan": [],
            "detailed_timing": {
                "seconds": [],
                "phase": [],
                "directions": {
                    "North-South-Left": [],
                    "North-South-Through": [],
                    "East-West-Left": [],
                    "East-West-Through": []
                }
            }
        }
        with open(f"tsp_plan_{i+1}_timing.json", "w") as f:
            json.dump(output_json, f, indent=2)