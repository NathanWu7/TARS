# TARS
Detailed algorithmic descriptions along with comprehensive experimental support for TARS

## Parameters
\begin{table*}[tbh]
    \centering
    \caption{Model Parameters}
    \label{tab:hyperparams}
    \begin{tabular}{llc}
    \toprule
    Parameter & Value  \\
    \midrule
    Number of points & 8192 \\
    Number of DownSample points & 2048 \\
    Number of each tactile sensor points & 64 \\
    Episode length of RL Training & 600 \\
    Episode length of student Training & 200 \\
    MLP layers of RL policy & 3 \\
    Units of RL mlp layers & 512 \\
    MLP layers of student policy & 3 \\
    Units of student mlp layers & 512 \\    
    SA modules of VTA & 4 \\
    FP modules of VTA & 4 \\
    Output dimension of Pointnet encoder & 16 \\
    Number of Gaussian distributions & 8 \\
    Conv layers of Pointnet encoder & 3 \\
    Activation function of Pointnet & ReLU \\
    Activation function of SAC & ELU \\
    Gamma of SAC & 0.99 \\
    Replay size of SAC & 2000 \\
    Replay size of student & 200 \\
    Batch size of student & 64 \\
    Number of parallel environments & 512 \\ 
    Epochs of Teacher & 50000 \\
    Epochs of Student & 50000 \\
    Optimizer & Adam \\
    Learning rate of SAC &  1e-3 \\
    Learning rate of VTP and VTA &  1e-4 \\
    Gradient clip value & 1.0 \\
    \bottomrule
    \end{tabular}
\end{table*}

\begin{table}[tbh]
    \centering
    \caption{Object Parameters}
    \label{tab:envparam}
    \begin{tabular}{llc}
    \toprule
    Object Parameter & Value  \\
    \midrule
    X-axis coordinate noise range & $\pm0.15m$ \\
    Y-axis coordinate noise range & $\pm0.15m$ \\
    Yaw axis orientation noise range & $\pm0.785rad$ \\
    \bottomrule
    \end{tabular}
\end{table}
