# scnet-hpc

在国产超算集群上工作的 [Claude Code](https://claude.com/claude-code) skill —— 从个人电脑配置连接、提交 Slurm 作业、交互式调试、排查失败。

面向超算互联网（scnet.cn）系列集群，支持多集群。集群参数存在 `clusters/*.conf`，脚本从 profile 读取，新增集群只需加一个配置文件。

## 为什么需要这个

国产超算的一些约束跟公有云/本地 GPU 机器差别很大，不知道就会反复踩：

- QOS 可能**强制每个作业申请加速器**，纯 CPU 作业直接被拒
- 内存上限是 `cpus-per-task × DefMemPerCPU`，想加内存**只能加 CPU 核数**
- 登录节点可能**缺共享库，import 不了 torch**——所有验证都得提交作业
- 计算节点**完全无外网**，任何运行时下载的库都会炸
- 作业脚本缺 `exit $rc` 会让 `sacct` **显示假的 COMPLETED**
- 国产加速器的软件栈落后于上游，**Triton 之类的基础设施可能整个不可用**，
  连带否掉一批推理框架

这些都写进了 skill，附带实测验证过的脚本。

## 安装

**如果你在用 Claude Code（或其他能执行命令的 AI 助手），直接把下面这段话发给它：**

> 帮我安装 scnet-hpc 这个 Claude Code skill。
> 从 https://github.com/lql341/scnet-hpc 克隆到本地（放哪都行，我不常动它），
> 然后运行仓库里的 `./scripts/install.sh`。
> 装完告诉我有哪些集群 profile 可用（`ls clusters/*.conf`）。
> 接着帮我配置连接：我的私钥在 `~/Downloads/` 下，是从超算平台控制台下载的
> `.txt` 文件，文件名形如 `<用户名>_<主机名>_RsaKeyExpireTime_<日期>.txt`。
> 用 `./scripts/setup-ssh.sh --cluster <集群短名> <私钥路径>` 配好并验证能连上。

它会自己找到私钥文件、挑对 profile、装好后测试连接。

**手工安装：**

```bash
git clone https://github.com/lql341/scnet-hpc.git
cd scnet-hpc
./scripts/install.sh
```

`install.sh` 装到用户级（所有项目可用），会自动识别 `CLAUDE_CONFIG_DIR`，
已有安装先备份。其他方式：

```bash
./scripts/install.sh --project    # 只装到当前项目的 .claude/skills/
./scripts/install.sh --link       # 符号链接，改仓库立即生效（开发用）
```

装完之后，Claude Code 里凡是涉及超算集群的任务会自动加载这个 skill，
也可以直接输入 `/scnet-hpc` 调用。

## 配置连接

从超算平台控制台下载私钥（`.txt` 文件），然后：

```bash
./scripts/setup-ssh.sh --cluster zzeshell ~/Downloads/你的用户名_<CLUSTER_HOST>_RsaKeyExpireTime_*.txt
```

只有一个集群 profile 时可省略 `--cluster`。用户名从私钥文件名自动推断。

脚本会做这些事，重复运行只补缺失项：

- 私钥装到 `~/.ssh/id_rsa_<集群短名>`，权限 600
- 写 `~/.ssh/config`（含长连接复用和保活，第二条命令起从 ~2s 降到 ~0.5s）
- macOS 上清除下载文件的隔离属性、启用 Keychain
- 测试连接并报告登录到了哪台节点

之后 `ssh <集群短名>` 直连，比如 `ssh zzeshell`。

出问题看 [`references/setup.md`](references/setup.md)——常见的是私钥过期或本机 IP
不在平台白名单（换网络后需要去控制台加）。

## 生成作业脚本

```bash
./scripts/new-job.sh --cluster zzeshell myjob 8 32 01:30:00    # 8 卡, 32 核, 1.5 小时
```

内存按 profile 里的 `DEF_MEM_PER_CPU` 自动算（这个集群超一点就被拒），并自动带上
`--gres`、`module load`、venv 激活、离线环境变量，以及那个关键的 `exit $rc`。

生成后按脚本给出的提示上传提交（它会打印带你用户名的完整命令）：

```bash
scp myjob.slurm zzeshell:/public/home/你的用户名/scripts/
ssh zzeshell 'mkdir -p ~/scripts/logs && sbatch --test-only ~/scripts/myjob.slurm'
```

`--test-only` 先验证配额合法，不真排队——返回 `Job N to start at <时间>` 就说明
参数没问题，去掉 `--test-only` 正式提交。

## 新增集群

**发给 AI 助手：**

> 我要把一个新的超算集群加进 scnet-hpc。集群信息：主机名 `<主机名>`，
> SSH 端口 `<端口>`，私钥在 `<路径>`。
> 先手工确认能 ssh 上去，然后用 `./scripts/probe-cluster.sh` 探测生成 profile，
> 补齐它探测不到的项（加速器架构要在计算节点跑 rocminfo 或 nvidia-smi 才知道），
> 最后用 `./scripts/setup-ssh.sh` 正式配好连接，并提交一个小作业验证。

**手工：**

```bash
# 1. 先临时加个 ssh 别名，确认能连上
# 2. 探测，自动填大部分字段
./scripts/probe-cluster.sh <ssh别名> <集群短名> > clusters/<集群短名>.conf
# 3. 补齐 profile 末尾列出的待确认项
# 4. ./scripts/setup-ssh.sh --cluster <集群短名> <私钥>
```

探测脚本会自动填调度器类型、分区、`DefMemPerCPU`、QOS 的 `MinTRES`、节点规格、
网络可达性、登录节点缺失的库等。探测不到的项留空并在末尾列出待确认清单，不瞎猜。

完整步骤（含加速器能力探针）见
[`references/adding-cluster.md`](references/adding-cluster.md)。

## 结构

```
SKILL.md                        主文件：通用约束、提交、调试
clusters/
├── _template.conf              新集群模板
├── zzeshell.conf               海光 BW1000 DCU（郑州）
└── kseshell.conf               海光 Z100 DCU（昆山）
scripts/
├── _common.sh                  profile 加载（被其他脚本 source）
├── setup-ssh.sh                配置 SSH 连接
├── probe-cluster.sh            探测集群生成 profile
├── new-job.sh                  生成作业脚本
└── install.sh                  安装 skill
references/
├── setup.md                    连接配置详解、平台差异
├── environment.md              环境栈、装依赖、目录约定、迁移注意
├── troubleshooting.md          排查手册、分层调试策略
└── adding-cluster.md           新增集群步骤、能力探针
```

## 已收录的集群

| 短名 | 描述 | 加速器 | 队列 |
|---|---|---|---|
| `zzeshell` | 超算互联网 · 郑州 | 海光 BW1000 DCU (gfx936) ×8/节点, 64GB/卡 | 仅 DCU（强制申请）|
| `kseshell` | 超算互联网 · 昆山 | 海光 Z100 DCU (gfx906) ×4/节点, 16GB/卡 | CPU 队列 + DCU 队列 |

两个集群的差异说明了为什么要把参数抽成 profile：

| | zzeshell | kseshell |
|---|---|---|
| SSH 端口 | 65032 | 65023 |
| `DefMemPerCPU` | 3888 MB | 3569 MB |
| 分区 | `hx1hdnormal`（唯一）| `kshcnormal` / `kshdnormal` / `kshdAI` |
| 纯 CPU 作业 | ❌ QOS 强制要 DCU | ✅ CPU 队列无此限制 |
| DTK 路径 | `compiler/dtk-26.04` | `compiler/rocm/dtk-26.04` |
| 加速器架构 | gfx936 | gfx906（更老，无 BF16/MFMA）|

## 隐私

仓库里不含私钥、token、个人用户名或密钥指纹。集群主机名和端口是平台公开信息。

`new-job.sh` 生成脚本时会把本机用户名展开进日志路径（`#SBATCH` 是注释行，
Slurm 不做变量展开，写 `$USER` 会导致作业失败），所以**生成的 `.slurm` 文件含
你的用户名**——`.gitignore` 已排除 `*.slurm`。

`.gitignore` 还排除了 `*.key`、`id_rsa*`、`*_RsaKey*` 等，避免误提交私钥。

## License

MIT
