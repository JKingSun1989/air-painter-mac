# 上传到自己的 GitHub 仓库

源码压缩包不包含本机 `.git`，因此不会带上原项目的远程地址或本机历史。请在解压后的干净目录中执行下面的操作，避免在开发目录中向上游仓库推送。

## 网页上传

1. 在 GitHub 新建自己的仓库，选择 Public；README、LICENSE 和 `.gitignore` 已在源码包内，无需另选模板。
2. 解压源码 ZIP，进入其中的 `air-painter-mac` 文件夹。
3. 将文件夹内的源码、文档、图片、`scripts/`、`tests/`、`third_party/` 和 `upstream/` 上传到仓库根目录；也带上 `.gitignore`。
4. 提交后确认首页显示本项目 README，图片正常显示，LICENSE 保留原作者声明。

ZIP 文件本身可作为 Release 附件；仓库首页要上传解压后的源码，单独上传 ZIP 不会展示 README 或让别人直接阅读代码。

## 使用 Git 推送

打开终端，进入解压后的 `air-painter-mac` 文件夹。把远程地址替换成你新建的仓库地址：

```bash
git init
git add .
git commit -m "Initial open source release"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/air-painter-mac.git
git push -u origin main
```

从解压目录初始化，而不是已有开发目录；开发目录原来的 origin 指向上游作者仓库。没有配置 Git 身份时，按 Git 提示设置自己的提交姓名和邮箱。GitHub 身份验证通过你自己的客户端完成，不要将令牌写入源码。

## 后续更新与打包

```bash
python3 scripts/package-source.py
```

生成 `dist/` 内的干净源码文件夹、ZIP、ZIP 的 SHA-256 校验文件和源码文件清单。打包只选择项目源码与公开文档；排除虚拟环境、模型、生成的 `.app`、缓存、设置、画作、测试输出和 Git 历史。

macOS 下载者按 README 执行 `./setup.sh`，在自己的 Mac 上安装环境并生成 `.app`；Windows 下载者双击 `setup_windows.cmd` 完成依赖安装，再双击 `start_windows.cmd` 启动。源码包不是独立运行的安装包，首次安装需要联网下载依赖与 MediaPipe 模型。
