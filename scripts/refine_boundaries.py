import json, pathlib, time
import numpy as np, trimesh, manifold3d as md
from scipy.spatial import cKDTree
R=pathlib.Path(__file__).resolve().parent.parent
log={}
def say(*s): print(*s,flush=True)
def manifold(mesh):
    a=md.Manifold(md.Mesh(mesh.vertices.astype(np.float32),mesh.faces.astype(np.uint32)))
    assert a.status()==md.Error.NoError,a.status()
    components=[c for c in a.decompose() if c.volume()>1e-10]
    return md.Manifold.batch_boolean(components,md.OpType.Add).set_tolerance(1e-5)
def mesh(a):
    t=a.to_mesh()
    return trimesh.Trimesh(np.asarray(t.vert_properties)[:,:3],np.asarray(t.tri_verts),process=False)
def union(values): return md.Manifold.batch_boolean(list(values),md.OpType.Add)

preferred=trimesh.load(R/'reference/preferred.glb',force='scene')
targeted=trimesh.load(R/'reference/targeted.glb',force='scene')
old={i:manifold(preferred.geometry[f'model_part{i}']) for i in range(17)}
new={i:manifold(targeted.geometry[f'model_part{i}']) for i in [1,5,6]}
cape_region=targeted.geometry['model_part1'].copy()
cape_region.vertices+=cape_region.vertex_normals*0.001
new[1]=manifold(cape_region)
affected=[9,12,13,14,16]
say('Union affected source parts')
U=union(old[i] for i in affected)
say('Affected source volume',U.volume())

# A closed cutter follows the hat/hair seam estimated from the source texture.
config=json.load(open(R/'reference/hat-boundary-fourier.json'))
a=np.array(config['coefficients']); cx,cz=config['center_xz']
N=360; vertices=[[cx,a[0],cz]]; faces=[]
angles=np.arange(N)*2*np.pi/N
f=np.full(N,a[0])
for n in range(1,5): f+=a[2*n-1]*np.cos(n*angles)+a[2*n]*np.sin(n*angles)
for radius in [.08,.16,.24,.32,.5,1.0]:
    yy=a[0]+(f-a[0])*min(radius/.16,1.)
    vertices.extend(np.column_stack([cx+radius*np.cos(angles),yy,cz+radius*np.sin(angles)]))
for j in range(N): faces.append([0,1+j,1+(j+1)%N])
for ring in range(5):
    s=1+ring*N;t=s+N
    for j in range(N):
        k=(j+1)%N;faces.extend([[s+j,t+j,t+k],[s+j,t+k,s+k]])
bottom=1+5*N;top=len(vertices)
vertices.extend(np.column_stack([cx+np.cos(angles),np.full(N,1.5),cz+np.sin(angles)]))
center=len(vertices);vertices.append([cx,1.5,cz])
for j in range(N):
    k=(j+1)%N;faces.extend([[bottom+j,top+j,top+k],[bottom+j,top+k,bottom+k],[center,top+k,top+j]])
cutter_mesh=trimesh.Trimesh(vertices,faces,process=True);cutter_mesh.fix_normals()
assert cutter_mesh.is_watertight
cutter=manifold(cutter_mesh)
say('Split hat along fitted seam')
upper=union([old[12],old[16]])
hat=upper^cutter
hair=upper-cutter
say('Hat and hair volumes',hat.volume(),hair.volume())
rear_box=md.Manifold.cube([2,3,1.04]).translate([-1,-1,-1])
root_band=cutter.translate([0,-.06,0])^rear_box
scalp=(old[9]^union([new[6],root_band]))-cutter
say('Reassigned scalp volume',scalp.volume())
hair=union([hair,scalp])
head=old[9]-scalp
say('Final hair volume',hair.volume())
say('Refine cape only against adjacent cloth and armor')
cloth=union([old[13],old[14]])
cape=cloth^new[1]
say('Cape volume',cape.volume())
armor=old[15]
say('Armor volume',armor.volume())
tunic=cloth-cape
say('Tunic volume',tunic.volume())
result={9:head,12:hat,13:cape,14:tunic,16:hair}
remnants=[]
say('Check preserved volume')
V=union(result.values())
missing=(U-V).volume();added=(V-U).volume()
log.update(affected_source_volume=U.volume(),corrected_volume=V.volume(),missing_volume=missing,added_volume=added,
           boundary_remnants=remnants,hat_boundary=config)
say('Volume differences',missing,added,'total',V.volume()-U.volume())
log['boolean_surface_tolerance_source_units']=1e-5
log['cape_cutter_outward_offset_source_units']=0.001
log['volume_difference_interpretation']='Signed Boolean difference is unreliable on overlapping/coincident source surfaces; use the independent multi-view exterior ray comparison for preservation checks.'

names={0:'taban',1:'sag-cizme',2:'el',3:'kalkan-detay',4:'sol-cizme',5:'kalkan-armasi',6:'kulak',7:'kalkan-merkez',8:'kalkan-govde',9:'bas',10:'pantolon',11:'kalkan-cerceve',12:'bere',13:'pelerin-atki',14:'tunik-kollar',15:'zirh',16:'sac'}
scene=trimesh.Scene();stats=[]
for i in range(17):
    m=mesh(result[i]) if i in result else preferred.geometry[f'model_part{i}'].copy()
    color=preferred.geometry[f'model_part{i}'].visual.vertex_colors[0]
    m.visual.vertex_colors=color
    scene.add_geometry(m,node_name=f'{i:02d}-{names[i]}',geom_name=f'{i:02d}-{names[i]}')
    stats.append({'index':i,'name':names[i],'faces':len(m.faces),'watertight':bool(m.is_watertight),'volume':float(m.volume),'changed':i in affected})
log['parts']=stats
scene.export(R/'models/model.glb')
json.dump(log,open(R/'reports/refinement-report.json','w'),indent=2)
say(json.dumps(log,indent=2))
