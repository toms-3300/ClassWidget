# ClassWidget

适用于 Windows 10/11 的中文桌面课程表小组件，使用 Python、PySide6 和 SQLite 开发。

> 当前仓库提供最新源码。最新界面调整尚未重新打包；仓库不包含旧版 EXE、个人课程数据库或虚拟环境。

## 功能

- 今日、迷你和周视图，通过系统托盘切换。
- 周视图星期纵向排列、课程横向排列，教学周旁按钮切换周次。
- 可视化课程管理，多时间安排、教学周、单双周、指定周次与冲突提示。
- 当天已结束课程淡化、添加删除线并后排。
- 课程卡片双侧色条、长名称自动缩字；悬停微放大、详情淡入展开，不推挤周围课程。
- 下一节课倒计时、Windows 系统通知及持久化防重复提醒。
- 浅色/深色、透明度、锁定位置、置顶和多显示器位置修正。
- JSON/CSV 导入导出、数据库备份恢复、用户主动开启的开机自启动。
- 不显示任务栏按钮，通过系统托盘显示、隐藏和退出；不使用 Explorer 桌面贴附机制。

## 安装与运行（Windows PowerShell）

安装 Python 3.12（64 位）。下载本仓库 ZIP 并解压，或使用 Git 克隆，然后在项目目录打开 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

首次安装成功后，可双击 **启动课程表.cmd**，以后无需重复安装。初次使用请通过托盘或窗口右键打开“课程管理与学期设置”，先设置学期，再添加自己的课程。

关闭小组件会隐藏到托盘；通过托盘“退出软件”完全退出。更新源码前先退出旧程序。

## 数据与提醒限制

课程数据库位于 `%LOCALAPPDATA%\ClassWidget\classwidget.db`，日志位于同目录的 `logs` 文件夹；窗口偏好由 QSettings 存储。升级代码前可从设置界面备份数据库。上传项目不会上传这些个人数据。

电脑关机、休眠或程序完全退出时，普通后台计时器不能保证准时提醒。程序运行和恢复后按补发策略处理；未声称支持离线提醒。Windows 通知、开机自启动、多显示器及不同 DPI 的实际效果需要在目标机器验证。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_*.py -q
$env:QT_QPA_PLATFORM='windows'
.\.venv\Scripts\python.exe tests\layout_smoke.py
.\.venv\Scripts\python.exe tests\window_smoke.py
```

测试使用隔离数据，不操作真实课程。详细交互说明见 [悬停交互说明](悬停交互说明.md)，更多操作见 [使用说明](使用说明.md)。

## 项目结构

```text
main.py                应用入口
app/database/          SQLite、迁移与持久化
app/services/          课程计算、提醒、系统集成与导入导出
app/ui/                小组件、课程管理、设置与卡片动画
assets/                图标与第三方许可文本
tests/                 自动化测试与界面检查
scripts/               源码启动、构建、预览与许可收集
```

## 可选打包

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

生成目录为 `dist/ClassWidget/`，分发时需保留完整目录。此次上传不构建 EXE。

## 第三方组件

见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 `assets/licenses/`。仓库公开不自动授予应用代码的开源许可；项目所有者尚未指定应用代码许可证。
