from RL.pc_vtafford.pcmodule import Network
from RL.pc_vtafford.rlmodule import Student
from RL.sac import MLPActorCritic

from torch.utils.tensorboard import SummaryWriter

import torch
import torch.optim as optim
import torch.nn as nn
import random
import numpy as np 

import copy
import os
import time
import open3d as o3d


class vtpolicy:
    def __init__(self,
                 vec_env,
                 cfg_train,
                 log_dir='run',
                 is_testing = False,
                 device='cpu'
                 ):
        self.is_testing = is_testing
        self.pc_debug = False
        self.pointCloudVisualizerInitialized = False

        self.vec_env = vec_env
        self.task_name = vec_env.task_name
        self.action_space = vec_env.action_space
        self.state_space = vec_env.state_space
        self.device = device
        self.cfg_train = cfg_train

        self.wo_tactile = self.cfg_train["with_tactile"]
        self.wo_VTA = self.cfg_train["with_Affordance"]

        self.pointclouds_shape = self.cfg_train["PCDownSampleNum"]
        self.tactile_shape = self.cfg_train["TDownSampleNum"] * 2
        self.cfg_train = copy.deepcopy(cfg_train)

        self.rl_algo = self.cfg_train["rl_algo"]
        self.rl_iter = self.cfg_train["rl_iter"]
        self.policy_iter = self.cfg_train["policy_iter"]

        self.latent_shape = self.cfg_train["latent_shape"]
        
        self.prop_shape = self.cfg_train["proprioception_shape"]
 
        self.input_shape = self.latent_shape + self.prop_shape 
        self.origin_shape =  self.cfg_train["origin_shape"]

        self.model_cfg = self.cfg_train["policy"]
        self.student_cfg = self.cfg_train["student"]
        self.learning_cfg = self.cfg_train["learn"]
        ac_kwargs = dict(hidden_sizes=[self.model_cfg["hidden_nodes"]]* self.model_cfg["hidden_layer"])

        self.learning_rate = self.learning_cfg["lr"]
        self.dagger_iter = 11

        self.log_dir = log_dir

        self.model_dir = os.path.join(log_dir,self.task_name) 
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)
        self.writer = SummaryWriter(log_dir=self.model_dir, flush_secs=10)
        self.actor_critic =  MLPActorCritic(self.origin_shape, vec_env.action_space, **ac_kwargs).to(self.device)
        self.student_actor = Student(self.input_shape, self.prop_shape, self.pointclouds_shape, self.latent_shape, self.action_space.shape, self.vec_env.num_envs, self.device, self.student_cfg)
        self.actor_critic.to(self.device)
        self.student_actor.to(self.device)
        
        print("##################")
        print("RL_model: ", os.path.join(self.model_dir,self.rl_algo+'_model_{}.pt'.format(self.rl_iter)))
        print()
        self.actor_critic.load_state_dict(torch.load(os.path.join(self.model_dir,self.rl_algo+'_model_{}.pt'.format(self.rl_iter))))
        self.actor_critic.eval()
        
        #self.encoded_obs = torch.zeros((self.vec_env.num_envs, self.input_shape), dtype=torch.float, device=self.device)

        self.TAN = Network(4, 16).to(device)
        self.TAN.load_state_dict(torch.load(os.path.join(self.model_dir,'TAN_model.pt')))
        self.TAN.eval()

        self.optimizer = optim.Adam([
	        {'params': self.student_actor.parameters(), 'lr': self.learning_rate,}
        	])
        self.criterion = nn.MSELoss()
        
        #debug
        self.policy_type = "VP"
        if self.wo_tactile == True:
            self.policy_type += "T"
        if self.wo_VTA == True:
            self.policy_type += "A"
        
        if self.pc_debug:
            from utils.o3dviewer import PointcloudVisualizer
            self.pointCloudVisualizer = PointcloudVisualizer()
            self.pointCloudVisualizerInitialized = False
            self.pcd = o3d.geometry.PointCloud()

    def eval(self, eval_step):
        current_obs = self.vec_env.reset()
        current_pcs = self.vec_env.get_pointcloud()
        all_cases = torch.zeros(( self.vec_env.num_envs),device = self.device)
        success_cases = torch.zeros(( self.vec_env.num_envs),device = self.device)
        print()
        print("#####################")
        print("Eval model: ", os.path.join(self.model_dir, self.policy_type+'_model_{}.pt'.format(self.policy_iter)))
        self.student_actor.load_state_dict(torch.load(os.path.join(self.model_dir, self.policy_type+'_model_{}.pt'.format(self.policy_iter))))
        self.student_actor.eval()
        pointclouds = torch.zeros((self.vec_env.num_envs, (self.pointclouds_shape + self.tactile_shape), 4), device = self.device)
        pcs = torch.zeros((self.vec_env.num_envs,self.pointclouds_shape,6),device = self.device)
        old_case = 0
        self.sample_shape = self.pointclouds_shape - self.tactile_shape

        while True:
            with torch.no_grad():
        
                pointclouds[:,:,0:3] = current_pcs[:,:,0:3]
                pcs[:,:,0:3] = pointclouds[:, -self.pointclouds_shape:, 0:3]

                if self.wo_tactile:
                    pcs[:,-self.tactile_shape:,4] = 1
                    pcs[:,:self.sample_shape,5] = 1
                else:
                    pcs[:,:,4] = 0
                    pcs[:,:,5] = 1
                 
                pcs[:,:,3] = 1

                if self.wo_VTA == True:
                    output = self.TAN(pcs[:,:,:4])
                    pcs[:,:,3] = output.detach()
                else:
                    pass

                mu, sigma, pi = self.student_actor.act(pcs,current_obs[:,:self.prop_shape])  
                action_pre = self.student_actor.mdn_sample(mu, sigma, pi)


                next_obs, rews, dones, successes,infos = self.vec_env.step(action_pre)
                success_cases += successes
                all_cases += dones
                if sum(all_cases) > 0:
                    cases = int(sum(all_cases).item())
                    succes_rate = round((sum(success_cases) / sum(all_cases)).item(),4)
                    if cases != old_case:
                        print("Task name: ",self.task_name, "Algo: {}".format(self.policy_type))
                        print("success_rate: ", succes_rate,"  in {} cases.".format(cases))
                        print()
                    if cases >= eval_step:
                        break
                    old_case = cases
                next_pointcloud = self.vec_env.get_pointcloud()  

                if self.pc_debug:
                    test = pcs[0, :, :3].cpu().numpy()

                    if self.wo_VTA == True:
                        color = output[0].unsqueeze(1).detach().cpu().numpy()
                        color = (color - min(color)) / (max(color)-min(color))
                        colors_blue = o3d.utility.Vector3dVector( color * [[1,0,0]])
                    else:
                        colors_blue = o3d.utility.Vector3dVector([[1,0,0]])

                    self.pcd.points = o3d.utility.Vector3dVector(list(test))
                    self.pcd.colors = o3d.utility.Vector3dVector(list(colors_blue))

                    if self.pointCloudVisualizerInitialized == False :
                        self.pointCloudVisualizer.add_geometry(self.pcd)
                        self.pointCloudVisualizerInitialized = True
                    else :
                        self.pointCloudVisualizer.update(self.pcd)
            
                # Step the vec_environment
                current_obs = next_obs
                current_pcs = next_pointcloud

    def run(self,num_learning_iterations=0,log_interval=1):
        model_dir = os.path.join(self.log_dir,self.task_name) 
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
        current_obs = self.vec_env.reset()
        current_pcs = self.vec_env.get_pointcloud()
        pointclouds = torch.zeros((self.vec_env.num_envs, (self.pointclouds_shape + self.tactile_shape), 4), device = self.device)

        update_step = 1
        iter = 6
        pcs = torch.zeros((self.vec_env.num_envs,self.pointclouds_shape,6),device = self.device)
        action_labels = torch.zeros((self.vec_env.num_envs, 7), device = self.device)
        self.sample_shape = self.pointclouds_shape - self.tactile_shape
               
        while True:
            beta = iter / (self.dagger_iter - 1)
            with torch.no_grad():
                action_labels = self.actor_critic.act(current_obs)   
            
                pointclouds[:,:,0:3] = current_pcs[:,:,0:3]
                pcs[:,:,0:3] = pointclouds[:, -self.pointclouds_shape:, 0:3]

                #different feature
                if self.wo_tactile == True:
                    pcs[:,-self.tactile_shape:,4] = 1
                    pcs[:,:self.sample_shape,5] = 1
                else:
                    pcs[:,:,4] = 0
                    pcs[:,:,5] = 1
                 
                pcs[:,:,3] = 1

                if self.wo_VTA == True:
                    output = self.TAN(pcs[:,:,:4])
                    pcs[:,:,3] = output.detach()
                else:
                    pass
                
                mu, sigma, pi = self.student_actor.act(pcs,current_obs[:,:self.prop_shape])    #[:,:self.prop_shape]
                action_pre = self.student_actor.mdn_sample(mu, sigma, pi)
                if random.random() < beta:
                    action_mix = action_labels
                else:
                    action_mix = action_pre

                #loss = self.student_actor.mdn_loss(mu, sigma, pi, action_labels)
                self.student_actor.add_transitions(pcs,current_obs[:,:self.prop_shape],action_labels)

            if self.student_actor.fullfill:
                data_pcs_batch,data_obs_batch, labels_batch = self.student_actor.batch_sampler()
                mu_batch, sigma_batch, pi_batch = self.student_actor.act(data_pcs_batch,data_obs_batch)
                loss = self.student_actor.mdn_loss(mu_batch, sigma_batch, pi_batch, labels_batch)

                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()       
                update_step += 1
                self.writer.add_scalar('Loss/Imitation', loss,update_step)      

            next_obs, rews, dones, successes, infos = self.vec_env.step(action_mix)
            next_pointcloud = self.vec_env.get_pointcloud()
            #counter[dones==1] = 0  

            if self.pc_debug:
                test = pcs[1, :, :3].cpu().numpy()
                #print(test.shape)
                if self.wo_VTA == True:
                    color = output[0].unsqueeze(1).detach().cpu().numpy()
                    color = (color - min(color)) / (max(color)-min(color))
                    colors_blue = o3d.utility.Vector3dVector( color * [[1,0,0]])
                else:
                    colors_blue = o3d.utility.Vector3dVector([[1,0,0]])
                #print(color * [[0,0,1]])
                self.pcd.points = o3d.utility.Vector3dVector(list(test))
                self.pcd.colors = o3d.utility.Vector3dVector(list(colors_blue))

                if self.pointCloudVisualizerInitialized == False :
                    self.pointCloudVisualizer.add_geometry(self.pcd)
                    self.pointCloudVisualizerInitialized = True
                else :
                    self.pointCloudVisualizer.update(self.pcd)  

            if update_step % log_interval == 0:
                print("Task name: ",self.task_name, "Algo: {}".format(self.policy_type))
                print("Save at:", update_step, " Iter:",iter, "  Loss: ", loss.item())
                print()
                if update_step >= num_learning_iterations:
                    torch.save(self.student_actor.state_dict(), os.path.join(self.model_dir, self.policy_type+ '_model_{}.pt'.format(update_step)))
                    break
                iter = iter + 1 if iter < 10 else 6

            if update_step % (log_interval * 10) == 0:
                torch.save(self.student_actor.state_dict(), os.path.join(self.model_dir, self.policy_type+'_model_{}.pt'.format(update_step)))

            current_obs = next_obs
            current_pcs = next_pointcloud


