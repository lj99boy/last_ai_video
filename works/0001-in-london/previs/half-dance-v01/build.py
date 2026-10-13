"""本地空间排演：仅验证走位、机位和接镜，不模拟脸、步态或布料。

运行：blender -b --python <本文件> -- [--render]
模型为比例代理，不作为生成参考上传。避免把机械代理运动传给成片。
"""
import bpy
import math
import json
import sys
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

WORK = Path(__file__).resolve().parents[2]
OUT = WORK / 'media/previs/half-dance-v01'
OUT.mkdir(parents=True, exist_ok=True)
FPS = 24
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 960, 540
scene.render.resolution_percentage = 100
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, 24 * FPS
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(OUT / 'frames/frame_')
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.background_type = 'WORLD'
scene.world.color = (.055, .065, .075)
scene.view_settings.view_transform = 'Standard'

def mat(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    return m

gold = mat('女主-金色位置代理', (.72,.47,.18))
dark = mat('男伴-深灰位置代理', (.17,.21,.25))
pink = mat('披肩-状态标记', (.68,.38,.41))
wall = mat('餐厅-蓝绿色', (.13,.25,.25))
cream = mat('桌面与门框', (.57,.52,.39))
floor = mat('地面', (.23,.21,.17))
red = mat('餐桌灯', (.58,.12,.065))
eye = mat('面部朝向标记', (.04,.045,.05))

def cube(name, loc, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale
    o.data.materials.append(material)
    return o

def sphere(name, loc, scale, material, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1, location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale
    o.data.materials.append(material)
    if parent: o.parent=parent
    return o

def rod(name, a, b, radius, material):
    d=Vector(b)-Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius, depth=d.length, location=(Vector(a)+Vector(b))/2)
    o=bpy.context.object; o.name=name; o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
    o.data.materials.append(material)
    return o

cube('地面',(0,2,-.12),(12,16,.2),floor)
# 门与通道为推定尺度，不能声称准确复建原画餐厅。
cube('门左立面',(-2,0,1.6),(5,.18,3.2),wall)
cube('门右立面',(4.5,0,1.6),(4,.18,3.2),wall)
cube('门楣',(1.5,0,3.0),(2.1,.28,.22),cream)
for x in [.48,2.52]: cube('门柱',(x,0,1.5),(.12,.22,3),cream)
cube('餐厅后墙',(0,8,1.8),(12,.2,3.6),wall)
for x in [-3.8,-1.3,3.8]:
    for y in [2.3,5.8]:
        cube('餐桌',(x,y,.78),(1.35,1.35,.12),cream)
        rod('桌腿',(x,y,0),(x,y,.74),.075,dark)
        rod('灯柱',(x,y,.84),(x,y,1.15),.035,cream)
        bpy.ops.mesh.primitive_cone_add(vertices=20,radius1=.2,radius2=.1,depth=.23,location=(x,y,1.18))
        bpy.context.object.data.materials.append(red)

door=bpy.data.objects.new('门轴',None);scene.collection.objects.link(door);door.location=(2.46,0,0)
leaf=cube('开门空间标记',(-.92,0,1.4),(1.84,.08,2.8),cream);leaf.parent=door

def person(name, material, height):
    root=bpy.data.objects.new(name,None);scene.collection.objects.link(root)
    k=height/1.72
    sphere(name+'躯干',(0,0,1.12*k),(.19,.11,.35*k),material,root)
    sphere(name+'头',(0,0,1.60*k),(.12,.105,.15*k),material,root)
    sphere(name+'鼻-朝向',(0,-.107,1.60*k),(.035,.035,.035),eye,root)
    for x in [-.09,.09]:
        sphere(name+'腿',(x,0,.49*k),(.065,.075,.42*k),material,root)
        sphere(name+'足',(x,-.05,.06),(.065,.14,.055),material,root)
    arms=[]
    for side in [-1,1]:
        for part in ['上臂','前臂']:
            o=rod(name+part,(0,0,0),(0,0,.3),.04,material);arms.append(o)
    return root,arms,k

female,fa,fk=person('女主',gold,1.72)
male,ma,mk=person('男伴',dark,1.83)
# 简单线廓仅标记裙子占地，绝不充当柔软裙料模拟。
bpy.ops.mesh.primitive_cone_add(vertices=24,radius1=.30,radius2=.145,depth=.92,location=(0,0,.49))
skirt=bpy.context.object;skirt.name='裙摆占地-非布料模拟';skirt.parent=female;skirt.data.materials.append(gold)
hat=sphere('帽子朝向',(0,-.02,1.79),(.23,.19,.045),dark,female)
wrap=sphere('披肩位置标记',(0,.04,1.35),(.25,.10,.065),pink,female)

bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam
cam.data.clip_start=.06;cam.data.clip_end=100

def mix(a,b,u):return Vector(a).lerp(Vector(b),max(0,min(1,u)))
def smooth(u):u=max(0,min(1,u));return u*u*(3-2*u)
def world(root,p): return root.location + root.rotation_euler.to_matrix() @ Vector(p)
def move_rod(o,a,b):
    d=Vector(b)-Vector(a);o.location=(Vector(a)+Vector(b))/2
    o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
    o.scale=(1,1,d.length/.3)
    o.keyframe_insert('location');o.keyframe_insert('rotation_euler');o.keyframe_insert('scale')

shots=[
 ('S012',0,3,'她发起邀请','medium'),
 ('S013a',3,8,'她行进转身：身段与裙摆','full'),
 ('S013b',8,10,'转身中接她的表情','close'),
 ('S014',10,12,'门开：注意转向入口','medium'),
 ('S003',12,17,'跨入暖光：完整着装','full'),
 ('S015',17,20,'侧向经过：持续前进','medium'),
 ('S005',20,24,'向后交披肩、右手到鬓边','full'),
]
for sid,start,end,title,scale in shots:
    scene.timeline_markers.new(sid+' '+title,frame=1+int(start*FPS))

audit=[]
for frame in range(1,scene.frame_end+1):
    scene.frame_set(frame);t=(frame-1)/FPS
    # 全片使用同一走位时间线，各机位切换不重置人物。
    angle=-1.35*smooth((t-3)/6.6)
    f=Vector((.8-.6*math.cos(angle),-2-.6*math.sin(angle),0))
    m=Vector((.8+.6*math.cos(angle),-2+.6*math.sin(angle),0))
    fy=math.pi/2+angle;my=-math.pi/2+angle
    if t>=9.6:
        u=smooth((t-9.6)/2.4)
        f=mix(f,(1.25,-.35,0),u);m=mix(m,(1.7,-1.1,0),u)
        fy=fy*(1-u)+math.pi*u;my=my*(1-u)+math.pi*u
    if t>=12:
        u=(t-12)/8
        f=mix((1.25,-.35,0),(.9,4.65,0),u)
        m=mix((1.7,-1.1,0),(1.6,3.95,0),u)
        fy=my=math.pi
    if t>=20:
        u=smooth((t-20)/2)
        f=mix((.9,4.65,0),(.5,4.95,0),u)
        m=mix((1.6,3.95,0),(1.2,4.5,0),u)
        fy=math.pi-.6*u;my=math.pi-.25*u
    female.location=f;male.location=m
    female.rotation_euler[2]=fy;male.rotation_euler[2]=my
    for root in [female,male]:
        root.keyframe_insert('location');root.keyframe_insert('rotation_euler')
    # 手臂仅标记动作方向，不能证明自然舞蹈或真实手部接触质量。
    joined=(f+m)/2+Vector((0,-.08,1.08))
    invite=smooth((t-.4)/1.5)
    release=smooth((t-9.7)/1)
    female_right=mix(world(female,(-.2,-.06,.94)),joined,invite*(1-release))
    male_left=mix(world(male,(.21,-.07,1.0)),joined,invite*(1-release))
    if t>=21:
        female_right=mix(female_right,world(female,(-.13,-.1,1.65)),smooth((t-21)/1.8))
    for root,arms,k,hands in [(female,fa,fk,[female_right,world(female,(.20,-.06,.94))]),(male,ma,mk,[world(male,(-.2,-.04,.96)),male_left])]:
        for j,side in enumerate([-1,1]):
            shoulder=world(root,(side*.19,0,1.34*k));hand=hands[j]
            elbow=(shoulder+hand)/2+Vector((side*.09,-.08,-.10))
            move_rod(arms[2*j],shoulder,elbow);move_rod(arms[2*j+1],elbow,hand)
    wrap.location=(0,.04+.55*smooth((t-20.4)/2),1.35-.22*smooth((t-20.4)/2))
    wrap.keyframe_insert('location')
    door.rotation_euler[2]=-1.52*smooth((t-10)/1.3);door.keyframe_insert('rotation_euler')
    sid,start,end,title,scale=next(s for s in shots if s[1]<=t<s[2])
    if t<3:
        cp=mix((2.8,-3.25,1.54),(2.55,-3.12,1.52),t/3);target=f+Vector((0,0,1.25));lens=45
    elif t<8:
        cp=mix((-1.55,-5.5,1.22),(-.75,-5.65,1.32),(t-3)/5);target=f+Vector((.20,.10,.9));lens=35
    elif t<10:
        cp=f+Vector((-.8,-2.1,1.63));target=f+Vector((0,0,1.54));lens=62
    elif t<12:
        cp=Vector((1.3,2.7,1.50));target=f+Vector((0,0,1.12));lens=40
    elif t<17:
        cp=f+Vector((-1.2,4.05,1.35));target=f+Vector((0,0,.9));lens=38
    elif t<20:
        cp=mix((-1.25,4.3,1.25),(-1.1,5.1,1.38),(t-17)/3);target=f+Vector((0,0,1.15));lens=32
    else:
        cp=mix((-1.0,7.55,1.55),(-.8,7.65,1.5),(t-20)/4);target=f+Vector((.15,0,.93));lens=29
    cam.location=cp;cam.rotation_euler=(target-cp).to_track_quat('-Z','Y').to_euler();cam.data.lens=lens
    cam.keyframe_insert('location');cam.keyframe_insert('rotation_euler');cam.data.keyframe_insert('lens')
    bpy.context.view_layer.update()
    points=[world_to_camera_view(scene,cam,f+Vector((0,0,z))) for z in [.015,1.86]]
    # 投影在画内不代表可见：另查门、墙、桌是否挡住头与躯干。
    blockers=[]
    for label,z in [('head',1.6),('torso',1.12)]:
        ray=f+Vector((0,0,z))-cp
        hit,loc,normal,index,obj,matrix=scene.ray_cast(bpy.context.evaluated_depsgraph_get(),cp,ray.normalized(),distance=ray.length)
        if hit and not (obj.name.startswith('女主') or obj.parent == female or obj.name.startswith('帽子') or obj.name.startswith('披肩')):
            blockers.append({'target':label,'object':obj.name})
    audit.append({'frame':frame,'time':round(t,4),'shot':sid,'scale':scale,'heroine_xy':[round(x,3) for x in f[:2]],'male_xy':[round(x,3) for x in m[:2]],'camera_xyz':[round(x,3) for x in cp],'feet_head_screen':[[round(p.x,4),round(p.y,4),round(p.z,4)] for p in points],'occlusion_candidates':blockers})

# 每帧显式采样，使用常量插值，避免跨切点自动飞越房间。
for action in bpy.data.actions:
    for layer in action.layers:
        for strip in layer.strips:
            for slot in action.slots:
                bag=strip.channelbag(slot)
                if bag:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:key.interpolation='CONSTANT'
(OUT/'projection-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
(OUT/'shots.json').write_text(json.dumps(shots,ensure_ascii=False,indent=2)+'\n')
scene.frame_set(110)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'half-dance-blocking.blend'))
if '--render' in sys.argv:
    bpy.ops.render.render(animation=True)
else:
    for frame in [25,110,210,258,350,435,540]:
        scene.frame_set(frame);scene.render.filepath=str(OUT/f'check-{frame:04d}.png');bpy.ops.render.render(write_still=True)
