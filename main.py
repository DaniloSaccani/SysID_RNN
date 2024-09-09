#!/usr/bin/env python
"""
Train an acyclic REN controller for the system of 2 robots in a corridor or 12 robots swapping positions.
Author: Danilo Saccani (danilo.saccani@epfl.ch)
"""

import torch
import numpy as np

from src.models import SystemRobots, Controller, TwoRobots
from src.plots import plot_trajectories, plot_traj_vs_time
from src.loss_functions import f_loss_states, f_loss_u, f_loss_ca, f_loss_obst
from src.utils import calculate_collisions, set_params
import matplotlib.pyplot as plt



torch.manual_seed(1)
# # # # # # # # Parameters and hyperparameters # # # # # # # #
params = set_params()
min_dist, t_end, n_agents, x0, xbar, linear, learning_rate, epochs, Q, \
alpha_u, alpha_ca, alpha_obst, n_xi, l, n_traj, std_ini, gammabar = params

# # # # # # # # Define models # # # # # # # #
#sys = SystemRobots(xbar, linear)
sys = TwoRobots(xbar,linear)
ctl = Controller(sys.f, sys.n, sys.m, n_xi, l, gammabar)
# # # # # # # # Define optimizer and parameters # # # # # # # #
optimizer = torch.optim.Adam(ctl.parameters(), lr=learning_rate)

print("------- Print open loop trajectories --------")

x_log = torch.zeros((t_end, sys.n))
u_log = torch.zeros((t_end, sys.m))
w_in = torch.randn((t_end + 1, sys.n))
w_in[0, :] = (x0)
u = torch.zeros(sys.m)
x = x0
for t in range(t_end):
    x, y = sys(t, x, u, w_in[t, :])
    x_log[t, :] = x
    u_log[t, :] = u
plot_trajectories(x_log, xbar, sys.n_agents, text="CL - before training", T=t_end, obst=alpha_obst)


# # # # # # # # Training # # # # # # # #
print("------------ Begin training ------------")
print("Problem: RH neurSLS -- t_end: %i" % t_end + " -- lr: %.2e" % learning_rate +
      " -- epochs: %i" % epochs + " -- n_traj: %i" % n_traj + " -- std_ini: %.2f" % std_ini)
print(" -- alpha_u: %.1f" % alpha_u + " -- alpha_ca: %i" % alpha_ca + " -- alpha_obst: %.1e" % alpha_obst)
print("REN info -- n_xi: %i" % n_xi + " -- l: %i" % l)
print("--------- --------- ---------  ---------")
for epoch in range(epochs):
    optimizer.zero_grad()
    lossl = np.zeros(epochs)
    loss_x, loss_u, loss_ca, loss_obst = 0, 0, 0, 0
    if epoch == 300:
        std_ini = 0.5
        optimizer.param_groups[0]['lr'] = optimizer.param_groups[0]['lr']
    for kk in range(n_traj):
        w_in = torch.randn(t_end + 1, sys.n)
        w_in[0, :] = x0.detach()
        u = torch.zeros(sys.m)
        x = x0
        xi = torch.zeros(ctl.psi_u.n_xi)
        omega = (x, u)
        for t in range(t_end):
            x, _ = sys(t, x, u, w_in[t, :])
            u, xi, omega = ctl(t, x, xi, omega)
            loss_x = loss_x + f_loss_states(t, x, sys, Q)
            loss_u = loss_u + alpha_u * f_loss_u(t, u)
            loss_ca = loss_ca + alpha_ca * f_loss_ca(x, sys, min_dist)
            if alpha_obst != 0:
                loss_obst = loss_obst + alpha_obst * f_loss_obst(x)
    loss = loss_x + loss_u + loss_ca + loss_obst
    print("Epoch: %i --- Loss: %.4f ---||--- Loss x: %.2f --- " % (epoch, loss / t_end, loss_x) +
          "Loss u: %.2f --- Loss ca: %.2f --- Loss obst: %.2f" % (loss_u, loss_ca, loss_obst))
    lossl[epoch] = loss.detach()
    loss.backward(retain_graph=True)
    optimizer.step()
    ctl.psi_u.set_model_param()

t = torch.linspace(0, epochs - 1, epochs)
plt.figure(figsize=(4 * 2, 4))
plt.subplot(1, 2, 1)
plt.plot(t, lossl[:])
plt.xlabel(r'$epoch$')
plt.title(r'$loss$')
# # # # # # # # Save trained model # # # # # # # #
torch.save(ctl.psi_u.state_dict(), "trained_models/OFFLINE_NeurSLS_tmp.pt")
# # # # # # # # Print & plot results # # # # # # # #
x_log = torch.zeros(t_end, sys.n)
u_log = torch.zeros(t_end, sys.m)
w_in = torch.randn(t_end + 1, sys.n)
w_in[0, :] = x0.detach()
u = torch.zeros(sys.m)
x = x0.detach()
xi = torch.zeros(ctl.psi_u.n_xi)
omega = (x, u)
for t in range(t_end):
    x, _ = sys(t, x, u, w_in[t, :])
    u, xi, omega = ctl(t, x, xi, omega)
    x_log[t, :] = x.detach()
    u_log[t, :] = u.detach()
plot_traj_vs_time(t_end, sys.n_agents, x_log, u_log)
# Number of collisions
n_coll = calculate_collisions(x_log, sys, min_dist)
print("Number of collisions after training: %d" % n_coll)
# Extended time
t_ext = t_end * 4
x_log = torch.zeros(t_ext, sys.n)
u_log = torch.zeros(t_ext, sys.m)
w_in = torch.randn(t_ext + 1, sys.n)
w_in[0, :] = x0.detach()
u = torch.zeros(sys.m)
x = x0.detach()
xi = torch.zeros(ctl.psi_u.n_xi)
omega = (x, u)
for t in range(t_ext):
    x, _ = sys(t, x, u, w_in[t, :])
    u, xi, omega = ctl(t, x, xi, omega)
    x_log[t, :] = x.detach()
    u_log[t, :] = u.detach()
plot_trajectories(x_log, xbar, sys.n_agents, text="CL - after training - extended t", T=t_end, obst=alpha_obst)


