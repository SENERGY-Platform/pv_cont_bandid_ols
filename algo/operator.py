"""
   Copyright 2022 InfAI (CC SES)

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

__all__ = ("Operator", )

import util
from . import aux_functions, agent, ols
import pickle
import pandas as pd
import numpy as np
import os
import astral
from astral import sun


class Operator(util.OperatorBase):
    def __init__(self, lat, long, power_history_start_stop='2', weather_dim=6, data_path="data", q=1, h=0.5):
        if not os.path.exists(data_path):
            os.mkdir(data_path)
        
        self.lat = float(lat)
        self.long = float(long)
        self.observer = astral.Observer(latitude=self.lat, longitude=self.long)

        self.weather_dim = weather_dim
        self.weather_same_timestamp = []
        self.power_history_start_stop = int(power_history_start_stop)
        self.history_power_len = pd.Timedelta(7,'days')
        self.power_history = []
        self.daylight_power_history = []

        self.agents = []

        self.agents_data = []

        self.actions_file = f'{data_path}/actions_{self.power_history_start_stop}.pickle'
        self.weather_file = f'{data_path}/weather_{self.power_history_start_stop}.pickle'
        self.agents_data_file = f'{data_path}/agents_data_{self.power_history_start_stop}.pickle'
        self.power_forecast_plot_file = f'{data_path}/histogram_{self.power_history_start_stop}.png'

        self.actions = []
        self.design_matrix_0, self.design_matrix_1, self.design_matrix = np.empty(shape=(0, 0)), np.empty(shape=(0, 0)), np.empty(shape=(0, 0))
        self.rewards_0, self.rewards_1 , self.rewards = [], [], []
        self.beta_hat_0, self.beta_hat_1 = np.zeros(self.weather_dim), np.zeros(self.weather_dim)
        self.beta_tilde_0, self.beta_tilde_1 = np.zeros(self.weather_dim), np.zeros(self.weather_dim)

        self.num_finished_agents_0 = 0
        self.num_finished_agents_1 = 1

        
        self.q = q
        self.h = h
        self.Tau = []
        self.nu_0 = ols.compute_nu_0(self.q, self.weather_dim)
        self.Tau_0 = [2*k for k in range(self.nu_0+1)]
        self.Tau_1 = [2*k+1 for k in range(self.nu_0+1)]

       
        #if os.path.exists(self.model_file):
        #    self.policy.load_state_dict(torch.load(self.model_file))

    def run_new_weather(self, new_weather_data):
        new_weather_array = aux_functions.preprocess_weather_data(new_weather_data)
        new_weather_input = np.mean(new_weather_array, axis=0)
        self.agents.append(agent.Agent())
        newest_agent = self.agents[-1]

        if len(self.Tau) in self.Tau_0:
            action = 0 
            newest_agent.timestep_in_Tau = True
        elif len(self.Tau) in self.Tau_1:
            action = 1
            newest_agent.timestep_in_Tau = True
        else:
            if np.abs((self.beta_tilde_0-self.beta_tilde_1).reshape(-1,1).transpose()@new_weather_input.reshape(1,-1)) > self.h/2:
                expected_reward_0 = self.beta_tilde_0.reshape(-1,1).transpose()@new_weather_input.reshape(1,-1)
                expected_reward_1 = self.beta_tilde_1.reshape(-1,1).transpose()@new_weather_input.reshape(1,-1)
                action = np.argmax([expected_reward_0, expected_reward_1])
            elif np.abs((self.beta_tilde_0-self.beta_tilde_1).reshape(-1,1).transpose()@new_weather_input.reshape(1,-1)) <= self.h/2:
                expected_reward_0 = self.beta_hat_0.reshape(-1,1).transpose()@new_weather_input.reshape(1,-1)
                expected_reward_1 = self.beta_hat_1.reshape(-1,1).transpose()@new_weather_input.reshape(1,-1)
                action = np.argmax([expected_reward_0, expected_reward_1])
            newest_agent.timestep_in_Tau = False

        self.Tau_0, self.Tau_1, self.Tau = ols.update_Taus(self.q, self.nu_0, self.Tau_0, self.Tau_1, self.Tau)        

        self.actions.append(action)

        newest_agent = self.agents[-1]
        newest_agent.save_weather_data(new_weather_input)
        newest_agent.initial_time = pd.to_datetime(new_weather_data[0]['weather_time']).tz_localize(None)
        newest_agent.action = self.actions[-1]

        self.design_matrix_0,  self.design_matrix_1, self.design_matrix= ols.update_design_matrices(self.design_matrix_0, self.design_matrix_1, self.design_matrix,
                                                                                                             new_weather_input, self.actions[-1])                                                       
    
        if newest_agent.action==0:
            return {"value": 0}
        elif newest_agent.action==1:
            return {"value": 1}

    def run_new_power(self, new_power_data):
        time, new_power_value = aux_functions.preprocess_power_data(new_power_data)
        if new_power_value != None:
            self.power_history.append((time,new_power_value))
            if time-self.power_history[0][0] > self.history_power_len:
                del self.power_history[0]
        sunrise = pd.to_datetime(sun.sunrise(self.observer, date=time, tzinfo='UTC')).tz_localize(None)
        sunset = pd.to_datetime(sun.sunset(self.observer, date=time, tzinfo='UTC')).tz_localize(None)
        if (sunrise+pd.Timedelta(self.power_history_start_stop, 'hours')<time) and (time+pd.Timedelta(self.power_history_start_stop, 'hours')<sunset):
            if new_power_value != None:
               self.daylight_power_history.append((time,new_power_value))
               if time-self.daylight_power_history[0][0] > self.history_power_len:
                   del self.daylight_power_history[0]

        old_agents = []
        old_indices = []
        
        for i, agent in enumerate(self.agents):
            if agent.initial_time + pd.Timedelta(2,'hours') >= time:
                if new_power_value != None:
                    agent.update_power_list(time, new_power_value)
            elif agent.initial_time + pd.Timedelta(2,'hours') < time:
                old_agents.append(agent)
                old_indices.append(i)

        old_indices = sorted(old_indices, reverse=True)
        for index in old_indices:
            del self.agents[index]
        for old_agent in old_agents:
            if old_agent.power_list != []:
                old_agent.reward = old_agent.get_reward(old_agent.action, [power for _, power in self.daylight_power_history])
                self.rewards.append(old_agent.reward)
                self.agents_data.append(old_agent)
                if old_agent.action==0:
                    self.rewards_0.append(old_agent.reward)
                    self.num_finished_agents_0 += 1
                elif old_agent.action==1:
                    self.rewards_1.append(old_agent.reward)
                    self.num_finished_agents_1 += 1
                if self.num_finished_agents_0 + self.num_finished_agents_1 >= 2*self.nu_0+3:
                    self.beta_hat_0, self.beta_hat_1, self.beta_tilde_0, self.beta_tilde_1 = ols.update_betas(old_agent.action, old_agent.timestep_in_Tau, self.Tau_0, self.Tau_1, 
                                                                                self.beta_hat_0, self.beta_hat_1,
                                                                                self.beta_tilde_0, self.beta_tilde_1,                             
                                                                                self.num_finished_agents_0, self.num_finished_agents_1, 
                                                                                self.design_matrix_0, self.design_matrix_1, self.design_matrix,
                                                                                self.rewards_0, self.rewards_1, self.rewards)
        with open(self.actions_file, 'wb') as f:
            pickle.dump(self.actions, f)
        with open(self.agents_data_file, 'wb') as f:
            pickle.dump(self.agents_data, f)

    def create_power_forecast(self, new_weather_data):
        power_forecast = []
        new_weather_array = aux_functions.preprocess_weather_data(new_weather_data)
        new_weather_forecasted_for = [pd.to_datetime(datapoint['forecasted_for']).tz_localize(None) for datapoint in new_weather_data]
        for i in range(0,len(new_weather_array),3):
            new_weather_input = np.mean(new_weather_array[i:i+3], axis=0)
            estimated_reward_0 = np.dot(new_weather_input, self.beta_hat_0)
            estimated_reward_1 = np.dot(new_weather_input, self.beta_hat_1)
            expected_action = np.argmax([estimated_reward_0, estimated_reward_1])
            if expected_action==0:
                expected_num = -1*estimated_reward_0
            elif expected_action==1:
                expected_num = estimated_reward_1
            power_forecast.append((new_weather_forecasted_for[i],expected_num))
        with open(self.power_forecast_plot_file, 'wb') as f:
            pickle.dump(power_forecast, f)
        return power_forecast
        
    def run(self, data, selector):
        print(selector + ": " + str(data))
        if selector == 'weather_func':
            if len(self.weather_same_timestamp)<47:
                self.weather_same_timestamp.append(data)
            elif len(self.weather_same_timestamp)==47:
                self.weather_same_timestamp.append(data)
                new_weather_data = self.weather_same_timestamp
                _ = self.run_new_weather(new_weather_data[0:3])
                power_forecast = self.create_power_forecast(new_weather_data)
                self.weather_same_timestamp = []
                return [{'timestamp':timestamp.strftime('%Y-%m-%d %X')+'Z', 'value': probability} for timestamp, probability in power_forecast]
        elif selector == 'power_func':
            self.run_new_power(data)
