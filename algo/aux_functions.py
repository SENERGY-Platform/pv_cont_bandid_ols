import numpy as np
import pandas as pd

def preprocess_power_data(new_power_data):
    time=pd.to_datetime(new_power_data['energy_time']).tz_localize(None)
    power = new_power_data['energy']
    return time, power


def preprocess_weather_data(new_weather_data):

    # Normalization of time (min=0, max=24), relative humidity (min=0, max=100), uv-index (min=0, max~10), cloud area fraction
    # (min=0, max=100) is easy. For temperature we choose min=-10, max=30 and for precipitation amount: min=0, max=10.

    aux_list = [[pd.to_datetime(data_point['weather_time']).tz_localize(None).hour/24, (data_point['instant_air_temperature']+10)/40, data_point['instant_relative_humidity']/100,
                 data_point['instant_ultraviolet_index_clear_sky']/10, data_point['1_hours_precipitation_amount']/10,
                 data_point['instant_cloud_area_fraction']/100] for data_point in new_weather_data]

    weather_array = np.array(aux_list)

    return weather_array
