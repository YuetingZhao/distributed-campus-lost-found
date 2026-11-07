# 项目已经做好后的操作（简版）

**项目：Distributed Campus Lost and Found（分布式校园失物招领系统）**

这个文件夹包含：完整 Python/Flask 项目、两个独立的 SQLite 节点、网页、双向同步、断网模拟、真正的并发冲突检测与人工解决、自动化测试、演示脚本、英文报告草稿 PDF 和口试准备材料。

## 1. 在 Mac 上运行

打开 Mac 的「终端」，进入**解压后的项目文件夹**（可以输入 `cd ` 后把文件夹拖进终端，按回车）。接着依次复制：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m scripts.run_both
```

在浏览器打开：

- Cesena：http://127.0.0.1:5001
- Forlì：http://127.0.0.1:5002

再打开一个终端，进入相同文件夹并执行：

```bash
./.venv/bin/python -m unittest discover -s tests -v
./.venv/bin/python -m scripts.demo
```

**第一次需要可以安装 Python 软件包的网络环境。** 如果程序启动报错，把完整错误复制给我即可。

## 2. 上传到你自己的 GitHub 仓库

老师已经允许你进行项目，现有仓库是：

https://github.com/YuetingZhao/distributed-campus-lost-found

最简单的方法：把本项目所有文件（包括隐藏的 `.github`、`.gitignore`）复制到你电脑上克隆的这个仓库文件夹中；然后在终端里执行：

```bash
git add .
git commit -m "Implement distributed lost and found prototype"
git push origin main
```

注意：**上面三条命令必须在克隆的 GitHub 仓库文件夹里运行**，不能在随便解压的文件夹里直接执行。可以先用 `git clone https://github.com/YuetingZhao/distributed-campus-lost-found.git` 克隆自己的仓库；原仓库如果有 README，复制项目文件时可以用本项目更完整的 README 替换。

如果你只想通过网页上传：进入仓库 → **Add file** → **Upload files**，上传项目文件并提交。网页上传隐藏文件和多级文件夹有时不方便，所以更推荐用 Git。

## 3. 报告在哪里？

- `docs/FINAL_REPORT_DRAFT.pdf`：已生成的英文课程报告**草稿**。
- `docs/FINAL_REPORT_DRAFT.md`：可修改的英文报告源文件。
- `docs/ORAL_DEMO_NOTES.md`：口试演示流程与问答。
- `README.md`：英文完整说明、接口、测试方法。

**在最终提交前还需要**：安装 Flask 后执行完整测试和演示，确认网页正常工作，将实测结果/截图写入报告；补上自己的正式姓名，按课程官方报告模板排版（如果课程要求）；再将最终 PDF 上传到课程论坛并等待老师确认。

> 特别说明：制作环境没有 Flask 库且无法联网安装，因此已经实际通过的是 7 项核心测试；2 项 Flask 路由测试被跳过。GitHub Actions 的自动化流程会在推送代码后安装 Flask、运行全部测试与双节点演示。
