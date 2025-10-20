import os
import sys
from typing import Optional

import yaml
import time

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log

cached_yaml_data: dict[str, dict] = {}  # yaml 缓存: {file_path: data}
_git_service_cache: Optional[object] = None  # 缓存 GitService 实例，避免循环依赖


def get_temp_config_path(file_path: str) -> str:
    """
    优先检查PyInstaller运行时的_MEIPASS目录下是否有对应的yml文件
    有则返回该路径，否则返回原路径
    """
    if hasattr(sys, '_MEIPASS'):
        mei_path = os.path.join(sys._MEIPASS, 'config', os.path.basename(file_path))
        if os.path.exists(mei_path):
            return mei_path
    return file_path


def read_yaml_from_git(file_path: str) -> Optional[dict]:
    """
    从 git HEAD 中读取 yaml 文件内容

    :param file_path: 文件的绝对路径
    :return: 解析后的 yaml 数据，失败时返回 None
    """
    global _git_service_cache

    start = time.perf_counter()
    attempted = False

    try:
        # 检查是否在 git 仓库中
        work_dir = os_utils.get_work_dir()
        git_dir = os.path.join(work_dir, '.git')
        if not os.path.exists(git_dir):
            return None

        # 计算相对路径
        try:
            relative_path = os.path.relpath(file_path, work_dir)
            # 确保使用正斜杠（git 标准）
            relative_path = relative_path.replace(os.sep, '/')
        except ValueError:
            # 文件不在工作目录中
            return None

        # 延迟导入避免循环依赖
        if _git_service_cache is None:
            from one_dragon.envs.git_service import GitService
            from one_dragon.envs.env_config import EnvConfig
            from one_dragon.envs.project_config import ProjectConfig

            # 创建配置对象
            project_config = ProjectConfig()
            env_config = EnvConfig()
            _git_service_cache = GitService(project_config, env_config)

        # 检查缓存
        attempted = True
        cached = cached_yaml_data.get(file_path)
        if cached is not None:
            elapsed_ms = (time.perf_counter() - start) * 1000
            log.debug(f"从 git 缓存加载 yaml: {file_path} (took {elapsed_ms:.3f} ms)")
            return cached

        # 从 git 中获取文件内容
        content = _git_service_cache.checkout_file_from_tree(relative_path)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if content is None:
            log.debug(f"从 git HEAD 未包含文件: {file_path} (took {elapsed_ms:.3f} ms)")
            return None

        # 解析 yaml
        data = yaml.safe_load(content)

        # 缓存数据
        cached_yaml_data[file_path] = data

        log.debug(f"从 git HEAD 加载 yaml: {file_path} (took {elapsed_ms:.3f} ms)")
        return data

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if attempted:
            log.debug(f'从 git 读取文件失败: {exc} (took {elapsed_ms:.3f} ms)')
        else:
            log.debug(f'从 git 读取文件失败: {exc}')
        return None


def read_cache_or_load(file_path: str):
    start = time.perf_counter()
    cached = cached_yaml_data.get(file_path)
    if cached is not None:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log.debug(f"从缓存加载 yaml: {file_path} (took {elapsed_ms:.3f} ms)")
        return cached

    with open(file_path, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)
        cached_yaml_data[file_path] = data
        elapsed_ms = (time.perf_counter() - start) * 1000
        log.debug(f"从磁盘加载 yaml: {file_path} (took {elapsed_ms:.3f} ms)")
        return data


class YamlOperator:

    def __init__(self, file_path: Optional[str] = None):
        """
        yml文件的操作器
        :param file_path: yml文件的路径。不传入时认为是mock，用于测试。
        """

        self.file_path: str = get_temp_config_path(file_path) if file_path else None
        """yml文件的路径"""

        self.data: dict = {}
        """存放数据的地方"""

        self.__read_from_file()

    def __read_from_file(self) -> None:
        """
        从yml文件中读取数据，优先级：缓存 > git HEAD > 磁盘
        :return:
        """
        if self.file_path is None:
            return

        # 1. 优先检查缓存
        cached = cached_yaml_data.get(self.file_path)
        if cached is not None:
            self.data = cached
            log.debug(f"从缓存读取配置: {self.file_path}")
            return

        # 2. 尝试从 git HEAD 读取
        git_data = read_yaml_from_git(self.file_path)
        if git_data is not None:
            self.data = git_data
            return

        # 3. 从文件系统读取
        if not os.path.exists(self.file_path):
            return

        try:
            self.data = read_cache_or_load(self.file_path)
        except Exception:
            log.error(f'文件读取失败 将使用默认值 {self.file_path}', exc_info=True)
            return

        if self.data is None:
            self.data = {}

    def save(self):
        if self.file_path is None:
            return

        with open(self.file_path, 'w', encoding='utf-8') as file:
            yaml.dump(self.data, file, allow_unicode=True, sort_keys=False)

    def save_diy(self, text: str):
        """
        按自定义的文本格式
        :param text: 自定义的文本
        :return:
        """
        if self.file_path is None:
            return

        with open(self.file_path, "w", encoding="utf-8") as file:
            file.write(text)

    def get(self, prop: str, value=None):
        return self.data.get(prop, value)

    def update(self, key: str, value, save: bool = True):
        if self.data is None:
            self.data = {}
        if key in self.data and not isinstance(value, list) and self.data[key] == value:
            return
        self.data[key] = value
        if save:
            self.save()

    def delete(self):
        """
        删除配置文件
        :return:
        """
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    @property
    def is_file_exists(self) -> bool:
        """
        配置文件是否存在
        :return:
        """
        return bool(self.file_path) and os.path.exists(self.file_path)
