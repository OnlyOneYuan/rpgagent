from pydantic import BaseModel, validator, ConfigDict
from agent.label.param import Param,ParamSet
from agent.label.talent import Talent
from typing import Dict, List, Optional
import pickle
import gc
from pathlib import Path

class RACE(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    param: ParamSet
    talents: List[Talent]


class Chara(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    param: ParamSet
    talents: List[Talent]
    race: RACE
    # job: JOB 后续加入

    def __init__(self, name: str, params: ParamSet, talents: List[Talent],race: RACE):
        super().__init__(name=name, param=params, talents=talents,race=race)
        self.talentsApply(params)

    def __str__(self):
        return self.name

    def params_levelup(self, name: str, difficulty: Optional[float] = None) -> bool:
        """升级指定参数（默认按该参数当前难度系数计算）"""
        return self.param.level_up(name, difficulty)

    def level_up(self, name: str, difficulty: Optional[float] = None) -> bool:
        """角色升级：提升指定参数等级，返回是否升级成功"""
        return self.param.level_up(name, difficulty)

    def add_talent(self, talent: Talent) -> bool:
        """升级时添加天赋：应用其效果并加入角色天赋列表；已存在则返回 False"""
        if talent in self.talents:
            return False
        talent.active = True
        self.talents.append(talent)
        self._arryApply(self.param, talent)
        return True

    def remove_talent(self, talent: Talent) -> bool:
        """升级时取消天赋：撤销其效果并从角色天赋列表移除；不存在则返回 False"""
        if talent not in self.talents:
            return False
        self._arryUnapply(self.param, talent)
        self.talents.remove(talent)
        talent.active = False
        return True

    def _param_map(self) -> Dict[str, Param]:
        """合并主参数与抗性参数，供天赋效果应用/撤销"""
        return {**self.param.params, **self.param.res}

    def _arryApply(self,params: ParamSet,talent: Talent):
        talent.apply_to_params(self._param_map())

    def _arryUnapply(self,params: ParamSet,talent: Talent):
        """撤销单个天赋对参数的效果"""
        talent.unapply_to_params(self._param_map())

    def talentsApply(self,params: ParamSet):
        for talent in self.talents:
            if talent.active:
                self._arryApply(params,talent)

    def raceApply(self,params: ParamSet,race: RACE):
        for talent in race.talents:
            self._arryApply(params,talent)
        for param in race.param.params:
            self.param.params[param.name].value = param.value
        

class CharaManager:
    """角色管理器，负责实例的追踪、修改标记与持久化存储"""
    
    def __init__(self, save_path: str = "characters.bin", batch_size: int = 1000):
        self.save_path = save_path
        self.batch_size = batch_size
        self._instances: List[Chara] = []
        self._modified_instances: List[Chara] = []

    def add(self, chara: Chara) -> None:
        """添加新角色并标记为已修改"""
        self._instances.append(chara)
        self.mark_as_modified(chara)
        
        if len(self._instances) % self.batch_size == 0:
            gc.collect()

    def mark_as_modified(self, chara: Chara) -> None:
        """标记指定实例为已修改"""
        if chara not in self._modified_instances:
            self._modified_instances.append(chara)

    def mark_as_saved(self, chara: Chara) -> None:
        """标记指定实例为已保存（从修改列表中移除）"""
        if chara in self._modified_instances:
            self._modified_instances.remove(chara)

    def add_talent(self, chara: Chara, talent: Talent) -> bool:
        """为角色添加天赋，并标记为已修改（下次保存时持久化）"""
        ok = chara.add_talent(talent)
        if ok:
            self.mark_as_modified(chara)
        return ok

    def remove_talent(self, chara: Chara, talent: Talent) -> bool:
        """为角色取消天赋，并标记为已修改（下次保存时持久化）"""
        ok = chara.remove_talent(talent)
        if ok:
            self.mark_as_modified(chara)
        return ok

    def save_all(self) -> None:
        """增量保存：只处理被修改或新增的实例"""
        if not self._modified_instances:
            return

        temp_path = f"{self.save_path}.tmp"
        
        try:
            # 1. 读取已有数据
            existing_data = []
            if Path(self.save_path).exists():
                with open(self.save_path, 'rb') as f:
                    while True:
                        try:
                            batch = pickle.load(f)
                            existing_data.extend(batch)
                        except EOFError:
                            break

            # 2. 合并数据：更新旧数据 + 追加新数据
            updated_data = []
            modified_names = {m.name for m in self._modified_instances}

            for instance in existing_data:
                if instance.name in modified_names:
                    # 找到同名且被修改的实例，替换为新实例
                    modified = next(m for m in self._modified_instances if m.name == instance.name)
                    updated_data.append(modified)
                    self.mark_as_saved(modified)
                else:
                    updated_data.append(instance)

            # 追加在文件中不存在的新实例
            existing_names = {d.name for d in existing_data}
            new_instances = [m for m in self._modified_instances if m.name not in existing_names]
            updated_data.extend(new_instances)
            for instance in new_instances:
                self.mark_as_saved(instance)

            # 3. 写入临时文件（分批写入）
            with open(temp_path, 'wb') as f:
                for i in range(0, len(updated_data), self.batch_size):
                    batch = updated_data[i:i + self.batch_size]
                    pickle.dump(batch, f)
                    gc.collect()
            
            # 4. 原子性替换原文件
            if Path(self.save_path).exists():
                Path(self.save_path).unlink()
            Path(temp_path).rename(self.save_path)
            
        except Exception as e:
            # 发生异常时清理临时文件
            if Path(temp_path).exists():
                Path(temp_path).unlink()
            raise e

    def load_all(self) -> List[Chara]:
        """加载所有实例到内存"""
        if not Path(self.save_path).exists():
            self._instances = []
            return self._instances
        
        instances = []
        try:
            with open(self.save_path, 'rb') as f:
                while True:
                    try:
                        batch = pickle.load(f)
                        instances.extend(batch)
                        gc.collect()
                    except EOFError:
                        break
        except Exception as e:
            raise e
        
        self._instances = instances
        self._modified_instances.clear()  # 加载后清空修改记录
        return self._instances