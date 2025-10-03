import bpy  # type: ignore
from ..properties.dynamic_properties import is_sms_dynamic, get_dynamic_name, refresh_template_list

# Global dictionary to store expand/collapse state for template groups
_group_expand_state = {}


class MadnessDynamicPanel(bpy.types.Panel):
    """Panel for SMS Dynamic Object properties"""
    bl_label = "Madness Dynamic Object"
    bl_idname = "OBJECT_PT_madness_dynamic"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return (context.object and
                context.object.type == 'EMPTY' and
                is_sms_dynamic(context.object))

    def draw(self, context):
        layout = self.layout
        obj = context.object
        dynamic_props = obj.madness_dynamic

        # Template Selection
        main_box = layout.box()
        main_box.label(text="Template Configuration", icon='LIBRARY_DATA_DIRECT')
        
        # Template selection
        row = main_box.row()
        if dynamic_props.template_name:
            row.prop(dynamic_props, "template_name", text="Template")
        else:
            row.operator("madness_dynamic.select_template", text="Select Template", icon='DOWNARROW_HLT')
        row.operator("madness_dynamic.refresh_templates", text="", icon='TRASH' if dynamic_props.template_name else 'FILE_REFRESH')
        
        if dynamic_props.template_name:
            # Mass Override
            mass_box = layout.box()
            mass_box.label(text="Mass Properties", icon='PHYSICS')
            mass_box.prop(dynamic_props, "use_mass_override")
            if dynamic_props.use_mass_override:
                mass_box.prop(dynamic_props, "mass")
            else:
                mass_box.label(text="Using template default mass", icon='INFO')

            # Material Override
            material_box = layout.box()
            material_box.label(text="Physics Material", icon='MATERIAL')
            material_box.prop(dynamic_props, "use_material_override")
            if dynamic_props.use_material_override:
                material_box.prop(dynamic_props, "physics_material")
            else:
                material_box.label(text="Using template default material", icon='INFO')

            # Scale Override
            scale_box = layout.box()
            scale_box.label(text="Collision Scale", icon='FULLSCREEN_ENTER')
            scale_box.prop(dynamic_props, "use_scale_override")
            if dynamic_props.use_scale_override:
                col = scale_box.column()
                col.prop(dynamic_props, "scale_x")
                col.prop(dynamic_props, "scale_y")
                col.prop(dynamic_props, "scale_z")
                scale_box.label(text="Note: Scale affects collision mesh size", icon='INFO')
            else:
                scale_box.label(text="Using object transform scale", icon='INFO')



class MADNESS_DYNAMIC_OT_select_template(bpy.types.Operator):
    """Select a dynamic object template"""
    bl_idname = "madness_dynamic.select_template"
    bl_label = "Select Template"
    bl_description = "Select a dynamic object template"

    def execute(self, context):
        # This will be handled by invoke with a menu
        return {'FINISHED'}

    def invoke(self, context, event):
        from ..properties.dynamic_properties import get_available_dynamic_templates
        
        # Get available templates
        try:
            templates = get_available_dynamic_templates()
            if len(templates) <= 1:  # Only empty template
                self.report({'WARNING'}, "No dynamic object templates available")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error loading templates: {e}")
            return {'CANCELLED'}
        
        # Create popup menu
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=400)

    def draw(self, context):
        from ..properties.dynamic_properties import get_available_dynamic_templates
        
        layout = self.layout
        obj = context.object
        
        if not obj or not is_sms_dynamic(obj):
            layout.label(text="No SMS_DYN object selected")
            return
        
        layout.label(text="Select Dynamic Object Template:", icon='LIBRARY_DATA_DIRECT')
        
        try:
            templates = get_available_dynamic_templates()
            
            # Organize templates into a hierarchical tree
            template_tree = self.organize_templates_into_tree(templates[1:])  # Skip empty first entry
            
            # Draw the hierarchical tree
            self.draw_template_tree(layout, template_tree, context)
                
        except Exception as e:
            layout.label(text=f"Error loading templates: {e}", icon='ERROR')

    def organize_templates_into_tree(self, templates):
        """Organize templates into groups based on common prefixes"""
        groups = {}
        
        for template_id, template_name, template_desc in templates:
            # Extract meaningful grouping from template name
            group_key = self.extract_group_key(template_name)
            
            if group_key not in groups:
                groups[group_key] = {
                    'display_name': group_key,
                    'templates': []
                }
            
            groups[group_key]['templates'].append((template_id, template_name, template_desc))
        
        return groups

    def extract_group_key(self, template_name):
        """Extract a meaningful group key from template name"""
        parts = template_name.split('_')
        
        # Handle different naming patterns
        if len(parts) >= 3:
            # For names like "rz_dyn_suzuka_distance_a_loda" -> "rz_dyn_suzuka"
            # For names like "dyn_trafficcone02_loda" -> "dyn_trafficcone"
            if parts[0] == 'rz' and parts[1] == 'dyn':
                # Race track specific objects: rz_dyn_trackname
                return '_'.join(parts[:3])
            elif parts[0] == 'dyn':
                # Generic dynamic objects: dyn_objecttype
                return '_'.join(parts[:2])
            else:
                # Other patterns: use first two parts
                return '_'.join(parts[:2])
        elif len(parts) >= 2:
            # Short names: use first two parts
            return '_'.join(parts[:2])
        else:
            # Single word: use as-is
            return template_name

    def draw_template_tree(self, layout, groups, context):
        """Draw the grouped template tree"""
        # Sort groups by display name
        sorted_groups = sorted(groups.items(), key=lambda x: x[1]['display_name'])
        
        for group_key, group_data in sorted_groups:
            # Create a collapsible box for each group
            box = layout.box()
            
            # Group header with expand/collapse toggle
            header = box.row()
            
            # Use global dictionary to track expanded state (collapsed by default)
            expand_key = f"dyn_expand_{group_key.replace('.', '_').replace('-', '_')}"
            
            # Get the expanded state from global dictionary
            expanded = _group_expand_state.get(expand_key, False)
            
            # Toggle button
            icon = 'TRIA_DOWN' if expanded else 'TRIA_RIGHT'
            toggle_op = header.operator("madness_dynamic.toggle_group", text="", icon=icon, emboss=False)
            toggle_op.group_key = group_key
            
            # Group name and item count
            header.label(text=group_data['display_name'], icon='FILE_FOLDER')
            header.label(text=f"({len(group_data['templates'])} items)")
            
            # Group contents (only show if expanded)
            if expanded:
                col = box.column(align=True)
                
                # Sort templates within the group
                sorted_templates = sorted(group_data['templates'], key=lambda x: x[1])
                
                for template_id, template_name, template_desc in sorted_templates:
                    row = col.row()
                    # Show the full template name
                    op = row.operator("madness_dynamic.set_template", text=template_name)
                    op.template_name = template_id

    def get_display_name_for_template(self, template_name, group_key):
        """Get a readable display name for the template within its group"""
        # Remove the group prefix to avoid redundancy
        if template_name.startswith(group_key):
            remaining = template_name[len(group_key):].lstrip('_')
            if remaining:
                # Format the remaining part
                return remaining.replace('_', ' ').title()
            else:
                # If nothing remains, use the full name
                return template_name.replace('_', ' ').title()
        else:
            # Fallback: use full name
            return template_name.replace('_', ' ').title()


class MADNESS_DYNAMIC_OT_toggle_group(bpy.types.Operator):
    """Toggle expand/collapse state of a template group"""
    bl_idname = "madness_dynamic.toggle_group"
    bl_label = "Toggle Group"
    bl_description = "Expand or collapse template group"

    group_key: bpy.props.StringProperty()
    operator_instance: bpy.props.IntProperty()

    def execute(self, context):
        # Use global dictionary to store state
        global _group_expand_state
        expand_key = f"dyn_expand_{self.group_key.replace('.', '_').replace('-', '_')}"
        
        # Toggle the expanded state
        current_state = _group_expand_state.get(expand_key, False)
        _group_expand_state[expand_key] = not current_state
        
        return {'FINISHED'}


class MADNESS_DYNAMIC_OT_set_template(bpy.types.Operator):
    """Set the template for the current dynamic object"""
    bl_idname = "madness_dynamic.set_template"
    bl_label = "Set Template"
    bl_description = "Set the template for the current dynamic object"

    template_name: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.object
        
        if not obj or not is_sms_dynamic(obj):
            self.report({'ERROR'}, "No SMS_DYN object selected")
            return {'CANCELLED'}
        
        obj.madness_dynamic.template_name = self.template_name
        self.report({'INFO'}, f"Template set to: {self.template_name}")
        return {'FINISHED'}


class MADNESS_DYNAMIC_OT_refresh_templates(bpy.types.Operator):
    """Refresh the list of available dynamic object templates"""
    bl_idname = "madness_dynamic.refresh_templates"
    bl_label = "Refresh Templates"
    bl_description = "Reload templates from master_dynamic_collisions.xml"

    def execute(self, context):
        refresh_template_list()
        self.report({'INFO'}, "Dynamic object templates refreshed")
        return {'FINISHED'}




def register():
    classes = [
        MadnessDynamicPanel,
        MADNESS_DYNAMIC_OT_select_template,
        MADNESS_DYNAMIC_OT_toggle_group,
        MADNESS_DYNAMIC_OT_set_template,
        MADNESS_DYNAMIC_OT_refresh_templates
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Already registered, unregister and re-register
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)


def unregister():
    classes = [
        MADNESS_DYNAMIC_OT_refresh_templates,
        MADNESS_DYNAMIC_OT_set_template,
        MADNESS_DYNAMIC_OT_toggle_group,
        MADNESS_DYNAMIC_OT_select_template,
        MadnessDynamicPanel
    ]
    
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass  # Already unregistered
