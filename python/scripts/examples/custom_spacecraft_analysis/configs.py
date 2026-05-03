""" =====================================================
The following python script is designed hold all the necessary
auxillary functions for running simultaions, that are not
specific to any given simulation.

Author James Tabony <james.tabony@attx.tech> : 10/31/25
===================================================== """

import os
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Union
from math import pi

def disperseDate(exc, year, month_range):
    '''
    Disperse the simulation start date according to month, day,
    and time dispersion range. For simplicity sake, this method
    does not use day and hour range as inputs, but they are dispersed.
    Days are dispersed uniformly between [1 28] for simplicity and
    hours are dispered between [1-24]

    INPUTS
    exc (SimulationExecutive):
    year (int):
        Year to disperse around, the year should go along with the
        month in the first element of the list.
    month_range (int[2]):
        List of months to disperse, where 1 -> January and 12 -> December.
        If the second number in the list is smaller than the first number,
        then it is assumed that the dispersion should loop across calender
        years.

    OUTPUT
    date (string):
        Date with dispersed day output
    '''
    # Check if month 2 is smaller than month 1 denoting a calender loop
    if month_range[1] < month_range[0]:
        start_month = exc.dispersions().createUniformInputDispersion("start_month",
                                                                     0.5*(month_range[0]+month_range[1]+12),
                                                                     month_range[0],
                                                                     month_range[1]+12)
        start_month = int(round(start_month()()))
        if start_month > 12:
            start_month = start_month - 12
            start_year = year + 1
        else:
            start_year = year
    # Otherwise disperse month as usual
    else:
        start_month = exc.dispersions().createUniformInputDispersion("start_month",
                                                                     0.5*(month_range[0]+month_range[1]),
                                                                     month_range[0],
                                                                     month_range[1])
        start_month = int(round(start_month()()))
        start_year = year
    
    # Compute the start day and start time
    start_day = exc.dispersions().createUniformInputDispersion("start_day",
                                                               14, 0, 28)
    start_day = int(round(start_day()()))

    start_time = exc.dispersions().createUniformInputDispersion("start_time",
                                                                12, 0, 24)
    start_time = int(round(start_time()()))

    return str(start_year) + " " + str(start_month) + " " + str(start_day) + " " + str(start_time) + ":00:00.000 MST"



def disperseOrbitParams(exc, altitude_range, inclination_range):
    '''
    Disperse the orbit elements of a circular orbit given ranges of the variable.
    Assumes that RAAN, argument of periapsis, and mean anomaly can be any value
    between -180 and 180 degrees.
    NOTE: All angles are in degrees

    INPUTS
    exc (SimulationExecutive):
    altitude_range (float[2]):
        Minimum and maximum altitude in meters to disperse
    inclination_range (float[2]):
        Minimum and maximum inclination in degrees to disperse

    OUTPUT
    orbit element list (float[6]):
        List of orbit elements to be input into dexstr.initializeState
        All angles are in degrees
    '''
    altitude = exc.dispersions().createUniformInputDispersion("altitude",
                                                              0.5*(altitude_range[0]+altitude_range[1]),
                                                              altitude_range[0],
                                                              altitude_range[1])
    altitude = altitude()()

    eccentricity = 0.0001

    inclination = exc.dispersions().createUniformInputDispersion("inclination",
                                                                 0.5*(inclination_range[0]+inclination_range[1]),
                                                                 inclination_range[0],
                                                                 inclination_range[1])
    inclination = inclination()()

    RAAN = exc.dispersions().createUniformInputDispersion("raan",
                                                          0.0, -180.0, 180.0)
    RAAN = RAAN()()

    argument_periapsis = exc.dispersions().createUniformInputDispersion("argument_periapsis",
                                                                        0.0, -180.0, 180.0)
    argument_periapsis = argument_periapsis()()

    mean_anomaly = exc.dispersions().createUniformInputDispersion("mean_anomaly",
                                                                  0.0, -180.0, 180.0)
    mean_anomaly = mean_anomaly()()

    return [altitude, eccentricity, inclination, RAAN, argument_periapsis, mean_anomaly]



def loadFilesMultiRun(path="results", filename="output.csv", runpath="run_"):
    """
    Function to load in an entire set of Monte Carlo results

    Params
    ------
    path - The master output directory into which all Monte Carlo results will be output
    filename - The filename we're interested in loading
    runpath - The prepend name for each individual MC output directory, i.e. run_ for run_1, run_2, etc.

    Return
    ------
    A list of all MC dataframes as [dfrun1, dfrun2, ...]
    """
    # Get a list of all directories
    dirs = os.listdir(path)
    # Sort directories containing runpath by the run number appended to runpath
    dirs.sort(key=lambda x: int(x[len(runpath):]) if runpath in x else -1)

    # Get a list of all directories matching our runpath output
    matchfiles = []
    for dirname in dirs:
        if runpath in dirname and dirname != runpath:
            matchfiles.append(os.path.join(path, dirname, filename))
    
    # Open dataframes from our file and return
    dfs = []
    for filename in matchfiles:
        if '.csv' in filename:
            dfs.append(pd.read_csv(filename))
        elif '.h5' in filename or '.hdf5' in filename:
            dfs.append(pd.read_hdf(filename))
        else:
            print("Skipping file " + filename + " with non-csv/non-hdf5 extension.")
    return dfs



def plotMcOverlay(x_key: str, y_keys: Union[str, List[str]], dataframes: List[pd.DataFrame],
                  x_label: str = None, y_labels: Union[str, List[str]] = None, titles: Union[str, List[str]] = None):
    """
    Plot one or more y-variables against a shared x-variable across multiple pandas DataFrames.

    The first DataFrame in the list is treated as the "nominal" case and is plotted in dark blue.
    All subsequent DataFrames are plotted in 50% transparent gray to visualize variation or spread.

    If multiple y-variables are specified, subplots are created in a single figure (one for each y-variable).
    If a single y-variable is specified, a single plot is generated.

    Parameters
    ----------
    x_key : str
        The name of the column to use as the x-axis variable.

    y_keys : str or List[str]
        One or more column names to use as y-axis variables. If a single string is provided,
        a single plot is generated. If a list is provided, subplots are created for each variable.

    dataframes : List[pd.DataFrame]
        A list of pandas DataFrames. Each DataFrame must contain the columns specified in `x_key` 
        and `y_keys`. The first DataFrame is treated as the reference or nominal case.

    Returns
    -------
    matplotlib fig
        The function generates matplotlib plots and returns it.
    """
    # Check that y_labels has the same size as y_keys if it was passed in
    if (y_labels is not None) and (isinstance(y_labels, list)) and (len(y_labels) != len(y_keys)):
        y_labels = None
        print("y_labels doesn't have the same length as y_keys - using y_keys as y_labels")

    # Check that titles has the same size as y_keys if it was passed in
    if (titles is not None) and (isinstance(titles, list)) and (len(titles) != len(y_keys)):
        titles = None
        print("titles doesn't have the same length as y_keys - using x/y_keys as titles")

    if isinstance(y_keys, str):
        y_keys = [y_keys]
        # single variable - one plot
        fig = plt.figure(figsize=(10, 5))
        for idx, df in enumerate(dataframes):
            color = 'darkblue' if idx == 0 else 'gray'
            alpha = 1.0 if idx == 0 else 0.5
            label = 'Nominal' if idx == 0 else None
            zorder = 10 if idx == 0 else 1  # Nominal line on top
            plt.plot(df[x_key][1:], df[y_keys[0]][1:], color=color, alpha=alpha, label=label, zorder=zorder)
        plt.xlabel(x_key) if x_label is None else plt.xlabel(x_label)
        plt.ylabel(y_keys[0]) if y_labels is None else plt.ylabel(y_labels)
        plt.title(f'{y_keys[0]} vs {x_key}') if titles is None else plt.title(titles)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
    else:
        # multiple variables - subplots
        n = len(y_keys)
        fig, axes = plt.subplots(n, 1, figsize=(10, 5 * n), sharex=True)
        if n == 1:
            axes = [axes]  # make it iterable if single subplot
        for ax, y_key in zip(axes, y_keys):
            for idx, df in enumerate(dataframes):
                color = 'darkblue' if idx == 0 else 'gray'
                alpha = 1.0 if idx == 0 else 0.5
                label = 'Nominal' if idx == 0 else None
                zorder = 10 if idx == 0 else 1  # Nominal line on top
                ax.plot(df[x_key][1:], df[y_key][1:], color=color, alpha=alpha, label=label, zorder=zorder)
            ax.set_ylabel(y_key) if y_labels is None else ax.set_ylabel(y_labels[y_keys.index(y_key)])
            (
                ax.set_title(f"{y_key} vs {x_key}")
                if (titles is None or not (isinstance(titles, list)))
                else ax.set_title(titles[y_keys.index(y_key)])
            )
            ax.legend()
            ax.grid(True)
        axes[-1].set_xlabel(x_key) if x_label is None else axes[-1].set_xlabel(x_label)
        plt.tight_layout()

    return fig
