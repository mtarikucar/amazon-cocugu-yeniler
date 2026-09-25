import bpy
from pathlib import Path
from mathutils import Vector
import numpy as np

ROOT=Path(__file__).resolve().parent.parent
bpy.ops.wm.read_factory_settings(use_empty=True)
comparison=bpy.context.scene
comparison.name='01 - Once ve sonra'
comparison.unit_settings.system='METRIC'
comparison.unit_settings.scale_length=.001

def import_model(path,label,offset):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    objects=[o for o in bpy.data.objects if o not in before and o.type=='MESH']
    pts=[o.matrix_world@Vector(v) for o in objects for v in o.bound_box]
    lo=np.min(pts,axis=0);hi=np.max(pts,axis=0)
    scale=150/(hi[2]-lo[2]);center=(hi+lo)/2;center[2]=lo[2]
    collection=bpy.data.collections.new(label)
    comparison.collection.children.link(collection)
    for o in objects:
        for c in list(o.users_collection): c.objects.unlink(o)
        collection.objects.link(o)
        o.data.transform(o.matrix_world);o.matrix_world.identity()
        v=np.empty(len(o.data.vertices)*3,dtype=np.float32)
        o.data.vertices.foreach_get('co',v)
        v=v.reshape((-1,3));v=(v-center)*scale;v[:,0]+=offset
        o.data.vertices.foreach_set('co',v.ravel());o.data.update()
        if o.data.color_attributes:
            o.color=tuple(o.data.color_attributes[0].data[0].color)
        o.name=label+' | '+o.name
    bpy.context.view_layer.update()
    return objects

previous=import_model(ROOT/'reference/preferred.glb','ONCE',-70)
final=import_model(ROOT/'models/model.glb','SONRA',70)
isolated=bpy.data.scenes.new('02 - Son 17 parca tek tek')
isolated.unit_settings.system='METRIC';isolated.unit_settings.scale_length=.001
coll=bpy.data.collections.new('SON PARCALAR');isolated.collection.children.link(coll)
for i,o in enumerate(sorted(final,key=lambda o:o.name)):
    c=o.copy();coll.objects.link(c)
    center=sum((Vector(v) for v in c.bound_box),Vector())/8
    c.location=Vector(((i%5-2)*90,0,(3-i//5)*95))-center
    c.show_name=True
note=bpy.data.texts.new('OKU')
note.write('01: Solda kullanicinin tercih ettigi onceki sonuc; sagda duzeltilmis sonuc.\n02: Duzenlenmis 17 parca tek tek.\nBirim: mm. Montaj yuksekligi 150 mm.\nRenkler parcalari gosterir; doku degildir.\nNumpad .: secime odaklan. /: secili parcayi yalniz goster. Home: tumunu goster.\n')
bpy.context.window.scene=comparison
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            s=area.spaces.active
            s.shading.type='SOLID';s.shading.color_type='OBJECT'
            s.shading.show_cavity=True
            s.overlay.show_floor=False;s.overlay.show_axis_x=False;s.overlay.show_axis_y=False
            r=s.region_3d;r.view_rotation=Vector((0,1,.1)).to_track_quat('Z','Y')
            r.view_perspective='ORTHO';r.view_distance=330;r.view_location=(0,0,75)
assert len(final)==17 and len(previous)==17
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'models/amazon-cocugu-yeniler.blend'),compress=True)
print('Verified Blender scenes: comparison 34 meshes, separated 17 meshes.')
