import numpy as np

def weighted_nanmedian(data, weights=None):
    """
    Compute the weighted median of a list.
    
    Parameters:
    - data (array-like): The data for which you want to compute the weighted median.
    - weights (array-like): The weights for each data point.
    
    Returns:
    - float: The weighted median.
    """

    if weights is None:
        weights = [1]*len(data)
    
    # Convert inputs to numpy arrays
    data = np.array(data)
    weights = np.array(weights, dtype=float)

    # Filter out NaN values in data or weights
    valid_data = ~np.isnan(data)
    valid_weights = ~np.isnan(weights)
    valid_indices = valid_data & valid_weights

    filtered_data = data[valid_indices]
    filtered_weights = weights[valid_indices]

    # If no valid data remains, return nan
    if len(filtered_data) == 0:
        return np.nan

    # Sort the data
    sorted_indices = np.argsort(filtered_data)
    sorted_data = filtered_data[sorted_indices]
    sorted_weights = filtered_weights[sorted_indices]

    # Compute the cumulative sum of weights
    cum_weights = np.cumsum(sorted_weights)

    # Find where the cumulative sum of weights exceeds half of total weight
    idx = np.where(cum_weights > cum_weights[-1] / 2.0)[0][0]

    return sorted_data[idx]

def weighted_nanmean(data, weights):
    # Convert inputs to numpy arrays
    data = np.array(data)
    weights = np.array(weights, dtype=float)

    # Ensure that weights associated with NaN data are also NaN
    weights[np.isnan(data)] = np.nan

    # Filter out NaN values in data or weights
    valid_data = ~np.isnan(data)
    valid_weights = ~np.isnan(weights)
    valid_indices = valid_data & valid_weights

    filtered_data = data[valid_indices]
    filtered_weights = weights[valid_indices]

    if len(filtered_data) == 0:
        return np.nan

    return np.average(filtered_data, weights=filtered_weights)

def weighted_nanstd(values, weights):
    """
    Return the weighted standard deviation while ignoring NaNs.

    values, weights -- Numpy ndarrays with the same shape.
    """
    # Convert inputs to numpy arrays
    values = np.array(values)
    weights = np.array(weights, dtype=float)

    # Ensure that weights associated with NaN values are also NaN
    weights[np.isnan(values)] = np.nan

    # Filter out NaN values in data or weights
    valid_values = ~np.isnan(values)
    valid_weights = ~np.isnan(weights)
    valid_indices = valid_values & valid_weights

    filtered_values = values[valid_indices]
    filtered_weights = weights[valid_indices]

    if len(filtered_values) == 0:
        return np.nan

    weighted_mean = np.average(filtered_values, weights=filtered_weights)
    variance = np.average((filtered_values - weighted_mean) ** 2, weights=filtered_weights)  # Weighted variance
    return np.sqrt(variance)