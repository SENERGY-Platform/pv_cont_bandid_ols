import numpy as np
from sklearn.linear_model import LinearRegression

def update_design_matrices(design_matrix_0, design_matrix_1, design_matrix, new_weather_input, action):
    if design_matrix.shape == (0,0):
       design_matrix_0 = new_weather_input.reshape((1,-1))
    else:
       design_matrix = np.vstack((design_matrix, new_weather_input)) 

    if action==0:
        if design_matrix_0.shape == (0,0):
            design_matrix_0 = new_weather_input.reshape((1,-1))
        else:
            design_matrix_0 = np.vstack((design_matrix_0, new_weather_input))
    elif action==1:
        if design_matrix_1.shape == (0,0):
            design_matrix_1 = new_weather_input.reshape((1,-1))
        else:
            design_matrix_1 = np.vstack((design_matrix_1, new_weather_input))
    return design_matrix_0, design_matrix_1, design_matrix

def update_actions(actions, beta_0, beta_1, new_weather_input):
    estimated_reward_0 = np.dot(new_weather_input, beta_0)
    estimated_reward_1 = np.dot(new_weather_input, beta_1)
    action = np.argmax([estimated_reward_0, estimated_reward_1])
    actions.append(action)
    return actions

def compute_nu_0(q, weather_dim):
    nu = 1 + np.ceil(1/q*np.log(2/(np.exp(q)-1)))
    nu_0 = max(nu, weather_dim+1)
    return nu_0

def update_Taus(q, nu_0, Tau_0, Tau_1, Tau):
    if Tau == []: # We use the length of Tau to implicitly track the number of time steps. This works because we append an element to Tau, every time we get new weather values.
        Tau = [1]
    else:
        Tau.append(np.exp(q*(len(Tau)+1)))

    if len(Tau) >= nu_0+1:
        if Tau[-1] >= 2*nu_0+2:
            Tau_0.append(Tau[-1])
            Tau_1.append(Tau[-1]+1)
        
    return Tau_0, Tau_1, Tau

def update_betas(action, timestep_in_Tau, Tau_0, Tau_1, beta_hat_0, beta_hat_1, beta_tilde_0, beta_tilde_1, num_finished_agents_0, 
                 num_finished_agents_1, design_matrix_0, design_matrix_1, design_matrix, rewards_0, rewards_1, rewards):
    if action==0:
        rewards_0_tr = np.array(rewards_0[:num_finished_agents_0]).reshape((-1,1))
        design_matrix_0_tr = design_matrix_0[:num_finished_agents_0]

        regressor = LinearRegression()
        regressor.fit(design_matrix_0_tr, rewards_0_tr)
        beta_hat_0 = regressor.coef_
    elif action==1:
        rewards_1_tr = np.array(rewards_1[:num_finished_agents_1]).reshape((-1,1))
        design_matrix_1_tr = design_matrix_1[:num_finished_agents_1]

        regressor = LinearRegression()
        regressor.fit(design_matrix_1_tr, rewards_1_tr)
        beta_hat_1 = regressor.coef_

    if timestep_in_Tau:
        if action==0:
            rewards_0_Tau_tr = np.array([rewards[i] for i in Tau_0]).reshape((-1,1))
            design_matrix_0_Tau_tr = design_matrix[Tau_0]

            regressor = LinearRegression()
            regressor.fit(design_matrix_0_Tau_tr, rewards_0_Tau_tr)
            beta_tilde_0 = regressor.coef_
        elif action==1:
            rewards_1_Tau_tr = np.array([rewards[i] for i in Tau_1]).reshape((-1,1))
            design_matrix_1_Tau_tr = design_matrix[Tau_1]

            regressor = LinearRegression()
            regressor.fit(design_matrix_1_Tau_tr, rewards_1_Tau_tr)
            beta_tilde_1 = regressor.coef_

    return beta_hat_0, beta_hat_1, beta_tilde_0, beta_tilde_1