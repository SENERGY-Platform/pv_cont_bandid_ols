class Agent:
    def __init__(self):
        self.initial_weather_data = None
        self.initial_time = None
        self.power_list = []
        self.action = None
        self.reward = None
        self.timestep_in_Tau = None
        
    def save_weather_data(self,weather_data):
        self.initial_weather_data = weather_data
        
    def update_power_list(self,time, new_power_value):
        self.power_list.append((time, new_power_value))
    
    def get_reward(self, action, history):
        agents_power_mean = sum([power_value for _, power_value in self.power_list])/len([power_value for _, power_value in self.power_list])
        history_mean = sum(history)/len(history)
        
        if action==1:    # 'YES'
            reward = agents_power_mean-history_mean
        elif action==0:  # 'NO'
            reward = history_mean-agents_power_mean
            
        return reward
        
