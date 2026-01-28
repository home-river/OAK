"""
配置格式转换器模块

职责：
- 提供 JSON 和 YAML 配置文件格式之间的转换功能
- 自动检测配置文件格式
- 处理依赖缺失的友好提示
- 支持 YAML 注释保持（使用 ruamel.yaml）

设计理念：
- 所有方法均为静态方法，无需实例化
- 格式检测基于文件扩展名
- 优先使用 ruamel.yaml（支持注释保持），回退到 PyYAML
- 提供友好的错误提示和库选择建议
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 尝试导入 ruamel.yaml（优先）
try:
    from ruamel.yaml import YAML
    HAS_RUAMEL_YAML = True
    logger.debug("使用 ruamel.yaml（支持注释保持和格式保持）")
except ImportError:
    HAS_RUAMEL_YAML = False
    logger.debug("ruamel.yaml 未安装，将回退到 PyYAML")

# 回退到 PyYAML
if not HAS_RUAMEL_YAML:
    try:
        import yaml as pyyaml
        HAS_PYYAML = True
        logger.debug("使用 PyYAML（不保留注释）")
    except ImportError:
        HAS_PYYAML = False


class ConfigConverter:
    """配置格式转换器（增强版）
    
    提供 JSON 和 YAML 配置文件格式之间的转换功能。
    支持 ruamel.yaml 注释保持功能，优先使用 ruamel.yaml，自动回退到 PyYAML。
    所有方法均为静态方法，无需实例化。
    
    支持的格式：
    - JSON (.json)
    - YAML (.yaml, .yml)
    
    YAML 库选择：
    - ruamel.yaml（推荐）：支持注释保持、格式保持、中文注释
    - PyYAML（回退）：基础 YAML 功能，不保留注释
    
    Example:
        # 检测格式
        format_type = ConfigConverter.detect_format(Path("config.json"))
        
        # JSON 转 YAML（保留注释）
        ConfigConverter.json_to_yaml(
            Path("config.json"),
            Path("config.yaml")
        )
        
        # YAML 转 JSON
        ConfigConverter.yaml_to_json(
            Path("config.yaml"),
            Path("config.json")
        )
    """
    
    @staticmethod
    def _get_yaml_handler() -> Optional[Any]:
        """获取 YAML 处理器
        
        优先使用 ruamel.yaml，回退到 PyYAML。
        每次调用时重新检查库的可用性。
        
        Returns:
            YAML 处理器实例（ruamel.yaml）或 None（PyYAML）
            
        Raises:
            ImportError: 两个库都未安装
        """
        # 尝试导入 ruamel.yaml
        try:
            from ruamel.yaml import YAML
            yaml = YAML()
            # 配置 ruamel.yaml
            yaml.preserve_quotes = True  # 保留引号风格
            yaml.default_flow_style = False  # 使用块风格
            yaml.allow_unicode = True  # 支持 Unicode（中文）
            yaml.width = 4096  # 避免长行自动换行
            logger.debug("使用 ruamel.yaml 处理器（支持注释保持）")
            return yaml
        except ImportError:
            pass
        
        # 回退到 PyYAML
        try:
            import yaml as pyyaml
            logger.warning(
                "使用 PyYAML 作为回退方案，注释将不会被保留。"
                "推荐安装 ruamel.yaml: pip install ruamel.yaml"
            )
            return None  # 使用 PyYAML 的全局函数
        except ImportError:
            pass
        
        # 两个库都未安装
        raise ImportError(
            "需要安装 YAML 库才能使用 YAML 配置\n"
            "推荐: pip install ruamel.yaml (支持注释保持)\n"
            "或: pip install pyyaml (基础功能)\n"
            "或: pip install oak_vision_system[yaml]"
        )
    
    @staticmethod
    def detect_format(file_path: Path) -> str:
        """检测配置文件格式
        
        基于文件扩展名识别配置文件格式。
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            str: "json" 或 "yaml"
            
        Raises:
            ValueError: 不支持的文件扩展名
            
        Example:
            >>> ConfigConverter.detect_format(Path("config.json"))
            'json'
            >>> ConfigConverter.detect_format(Path("config.yaml"))
            'yaml'
        """
        suffix = file_path.suffix.lower()
        
        if suffix == ".json":
            return "json"
        elif suffix in [".yaml", ".yml"]:
            return "yaml"
        else:
            raise ValueError(
                f"不支持的文件格式: {suffix}，支持的格式: .json, .yaml, .yml"
            )
    
    @staticmethod
    def json_to_yaml(input_path: Path, output_path: Path) -> None:
        """将 JSON 配置转换为 YAML 格式
        
        读取 JSON 文件，转换为 YAML 格式并保存。
        使用 ruamel.yaml（如果可用）以支持注释保持。
        
        Args:
            input_path: 输入 JSON 文件路径
            output_path: 输出 YAML 文件路径
            
        Raises:
            FileNotFoundError: 输入文件不存在
            json.JSONDecodeError: JSON 格式错误
            ImportError: YAML 库未安装
            OSError: 文件读写错误
            
        Example:
            >>> ConfigConverter.json_to_yaml(
            ...     Path("config.json"),
            ...     Path("config.yaml")
            ... )
        """
        # 1. 检查文件存在
        if not input_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {input_path}")
        
        # 2. 获取 YAML 处理器（会检查依赖）
        yaml_handler = ConfigConverter._get_yaml_handler()
        
        # 3. 读取和解析 JSON
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"JSON 解析失败: {e.msg}, path={input_path}",
                e.doc,
                e.pos
            )
        except OSError as e:
            raise OSError(f"文件读取失败: {e}, path={input_path}")
        
        # 4. 写入 YAML
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # 检查使用的是哪个库
                try:
                    from ruamel.yaml import YAML
                    # ruamel.yaml: 保留注释和格式
                    yaml_handler.dump(data, f)
                    logger.info(f"配置已转换（使用 ruamel.yaml）: {input_path} → {output_path}")
                except ImportError:
                    # PyYAML: 不保留注释
                    import yaml as pyyaml
                    pyyaml.dump(
                        data,
                        f,
                        allow_unicode=True,
                        default_flow_style=False,
                        sort_keys=False
                    )
                    logger.info(f"配置已转换（使用 PyYAML）: {input_path} → {output_path}")
        except OSError as e:
            raise OSError(f"文件写入失败: {e}, path={output_path}")
    
    @staticmethod
    def yaml_to_json(input_path: Path, output_path: Path) -> None:
        """将 YAML 配置转换为 JSON 格式
        
        读取 YAML 文件，转换为 JSON 格式并保存。
        使用 ruamel.yaml（如果可用）以支持注释保持。
        
        Args:
            input_path: 输入 YAML 文件路径
            output_path: 输出 JSON 文件路径
            
        Raises:
            FileNotFoundError: 输入文件不存在
            yaml.YAMLError: YAML 格式错误
            ImportError: YAML 库未安装
            OSError: 文件读写错误
            
        Example:
            >>> ConfigConverter.yaml_to_json(
            ...     Path("config.yaml"),
            ...     Path("config.json")
            ... )
        """
        # 1. 检查文件存在
        if not input_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {input_path}")
        
        # 2. 获取 YAML 处理器（会检查依赖）
        yaml_handler = ConfigConverter._get_yaml_handler()
        
        # 3. 读取和解析 YAML
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                # 检查使用的是哪个库
                try:
                    from ruamel.yaml import YAML
                    # ruamel.yaml: 保留注释信息
                    data = yaml_handler.load(f)
                except ImportError:
                    # PyYAML: 不保留注释
                    import yaml as pyyaml
                    data = pyyaml.safe_load(f)
        except Exception as e:
            # 统一处理 YAML 错误
            raise Exception(f"YAML 解析失败: {e}, path={input_path}")
        
        # 4. 写入 JSON
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            raise OSError(f"文件写入失败: {e}, path={output_path}")
        
        # 5. 记录日志
        try:
            from ruamel.yaml import YAML
            logger.info(f"配置已转换（使用 ruamel.yaml）: {input_path} → {output_path}")
        except ImportError:
            logger.info(f"配置已转换（使用 PyYAML）: {input_path} → {output_path}")
    
    @staticmethod
    def load_yaml_as_dict(file_path: Path) -> Dict[str, Any]:
        """加载 YAML 文件为字典（保留注释信息）
        
        读取 YAML 文件并解析为 Python 字典。
        使用 ruamel.yaml（如果可用）以支持注释保持。
        
        Args:
            file_path: YAML 文件路径
            
        Returns:
            dict: 配置字典
            
        Raises:
            ImportError: YAML 库未安装
            Exception: YAML 格式错误
            OSError: 文件读取错误
            
        Example:
            >>> config = ConfigConverter.load_yaml_as_dict(Path("config.yaml"))
            >>> print(config["config_version"])
            '2.0.0'
        """
        # 1. 获取 YAML 处理器（会检查依赖）
        yaml_handler = ConfigConverter._get_yaml_handler()
        
        # 2. 读取和解析 YAML
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 检查使用的是哪个库
                try:
                    from ruamel.yaml import YAML
                    # ruamel.yaml: 保留注释
                    data = yaml_handler.load(f)
                except ImportError:
                    # PyYAML: 不保留注释
                    import yaml as pyyaml
                    data = pyyaml.safe_load(f)
            return data
        except Exception as e:
            raise Exception(f"YAML 文件读取失败: {e}, path={file_path}")
    
    @staticmethod
    def save_as_yaml(
        config_dict: Dict[str, Any], 
        output_path: Path,
        preserve_comments: bool = True
    ) -> None:
        """保存字典为 YAML 文件（保留注释）
        
        将 Python 字典序列化为 YAML 格式并保存。
        使用 ruamel.yaml（如果可用）以支持注释保持。
        
        配置：
        - UTF-8 编码
        - 无流式风格（default_flow_style=False）
        - 不排序键（sort_keys=False）
        - 支持 Unicode（allow_unicode=True）
        - 保留引号风格（ruamel.yaml）
        
        Args:
            config_dict: 配置字典
            output_path: 输出文件路径
            preserve_comments: 是否尝试保留注释（需要 ruamel.yaml）
            
        Raises:
            ImportError: YAML 库未安装
            OSError: 文件写入错误
            
        Example:
            >>> config = {"config_version": "2.0.0", "test": "value"}
            >>> ConfigConverter.save_as_yaml(config, Path("config.yaml"))
        """
        # 1. 获取 YAML 处理器（会检查依赖）
        yaml_handler = ConfigConverter._get_yaml_handler()
        
        # 2. 写入 YAML
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # 检查使用的是哪个库
                try:
                    from ruamel.yaml import YAML
                    # ruamel.yaml: 保留注释和格式
                    yaml_handler.dump(config_dict, f)
                except ImportError:
                    # PyYAML: 不保留注释
                    import yaml as pyyaml
                    pyyaml.dump(
                        config_dict,
                        f,
                        allow_unicode=True,
                        default_flow_style=False,
                        sort_keys=False
                    )
        except OSError as e:
            raise OSError(f"YAML 文件写入失败: {e}, path={output_path}")
