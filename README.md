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

```bash
git clone https://github.com/<你的用户名>/scnet-hpc.git
cd scnet-hpc
./scripts/install.sh              # 装到用户级，所有项目可用
```

其他方式：

```bash
./scripts/install.sh --project    # 只装到当前项目的 .claude/skills/
./scripts/install.sh --link       # 符号链接，改仓库立即生效（开发用）
```

会自动识别 `CLAUDE_CONFIG_DIR`，已有安装会先备份。

## 配置连接

从超算平台控制台下载私钥，然后：

```bash
./scripts/setup-ssh.sh ~/Downloads/<用户名>_<主机>_RsaKeyExpireTime_*.txt
```

脚本会装私钥（600）、写 `~/.ssh/config`（含长连接和保活）、测试连接。
macOS 上额外清除下载文件的隔离属性并启用 Keychain。**幂等**，重复运行只补缺失项。

有多个集群 profile 时加 `--cluster <短名>`。

## 生成作业脚本

```bash
./scripts/new-job.sh myjob 8 32 01:30:00    # 8 卡, 32 核, 1.5 小时
```

内存按 profile 里的 `DEF_MEM_PER_CPU` 自动算，避免手算超限；自动带上
`--gres`、`module load`、venv 激活、离线环境变量、以及那个关键的 `exit $rc`。

## 新增集群

```bash
# 先手工确认能 ssh 上去，然后：
./scripts/probe-cluster.sh <ssh别名> <集群短名> > clusters/<集群短名>.conf
```

探测脚本会自动填调度器类型、分区、`DefMemPerCPU`、QOS 的 `MinTRES`、节点规格、
网络可达性、登录节点缺失的库等。探测不到的项留空并在末尾列出待确认清单，不瞎猜。

完整步骤见 [`references/adding-cluster.md`](references/adding-cluster.md)。

## 结构

```
SKILL.md                        主文件：通用约束、提交、调试
clusters/
├── _template.conf              新集群模板
└── zzeshell.conf               海光 DCU 集群（郑州）
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

| 短名 | 描述 | 加速器 |
|---|---|---|
| `zzeshell` | 超算互联网 · 郑州 | 海光 BW1000 DCU (gfx936) ×8/节点 |

## 隐私

仓库里不含私钥、token、个人用户名或密钥指纹。集群主机名和端口是平台公开信息。
作业脚本模板用 `$USER` 而非硬编码用户名。

`.gitignore` 排除了 `*.key`、`id_rsa*`、`*_RsaKey*` 等，避免误提交私钥。

## License

MIT
