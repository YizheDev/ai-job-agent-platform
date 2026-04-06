# AI 求职智能管家

## 运行方式

请优先使用项目虚拟环境中的 Python 运行：

```powershell
C:\Users\BQ4\Desktop\project\.venv\Scripts\python.exe main.py
```

不要直接使用：

```powershell
py main.py
```

原因是 `py` 可能会调用系统 Python，而不是项目的 `.venv`。如果系统 Python 没有安装项目依赖，就会出现例如：

```text
ModuleNotFoundError: No module named 'pydantic'
```

## 安装依赖

如果 `.venv` 尚未安装依赖，请执行：

```powershell
C:\Users\BQ4\Desktop\project\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
