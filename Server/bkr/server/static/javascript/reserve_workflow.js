ReserveWorkflow = function (arch,distro_family,method,tag,distro,submit,auto_pick,arch_val,distro_family_val,tag_val,method_val,
                            all_arches,all_distro_familys,all_tags,all_methods) {
    this.arch_id = arch
    this.distro_family_id = distro_family
    this.method_id = method
    this.tag_id = tag
    this.distro_id = distro 
    this.submit_id = submit
    this.auto_pick_id = auto_pick

    this.arch_val = arch_val
    this.distro_family_val = distro_family_val
    this.method_val = method_val
    this.tag_val = tag_val

    this.all_arches = all_arches
    this.all_distro_familys = all_distro_familys
    this.all_tags = all_tags
    this.all_methods = all_methods
    bindMethods(this)
};

ReserveWorkflow.prototype.initialize = function() {  
    getElement(this.submit_id).setAttribute('disabled',1) 
    getElement(this.auto_pick_id).setAttribute('disabled',1)
    this.replace_fields() 
}

ReserveWorkflow.prototype.replace_fields = function() {  
    // For some stupid reason I can't get a closure to work in JS...so I'm writing all this redundant code
    // what a pita
    replaceChildNodes(this.arch_id, map(this.replaceArch ,this.all_arches))
    replaceChildNodes(this.distro_family_id, map(this.replaceDistroFamily ,this.all_distro_familys))
    replaceChildNodes(this.tag_id, map(this.replaceTag ,this.all_tags))
    $("#"+this.tag_id+" option[value='STABLE']").attr('selected', 'selected') //SET default tag as 'STABLE'
    replaceChildNodes(this.method_id, map(this.replaceMethod ,this.all_methods))
}


ReserveWorkflow.prototype.replaceMethod = function(arg) { 
        if ( arg[0] == this.method_val ) {
            option = OPTION({"value": arg[0],
                             "selected": true}, arg[1]);
        } else {
            option = OPTION({"value": arg[0]}, arg[1]);
        }
        return option;
}
ReserveWorkflow.prototype.replaceDistroFamily = function(arg) { 
        if ( arg[0] == this.distro_family_val ) {
            option = OPTION({"value": arg[0],
                             "selected": true}, arg[1]);
        } else {
            option = OPTION({"value": arg[0]}, arg[1]);
        }
        return option;
}

ReserveWorkflow.prototype.replaceTag = function(arg) { 
        if ( arg[0] == this.tag_val ) {
            option = OPTION({"value": arg[0],
                             "selected": true}, arg[1]);
        } else {
            option = OPTION({"value": arg[0]}, arg[1]);
        }
        return option;
}

ReserveWorkflow.prototype.replaceArch = function(arg) { 
        if ( arg[0] == this.arch_val ) {
            option = OPTION({"value": arg[0],
                             "selected": true}, arg[1]);
        } else {
            option = OPTION({"value": arg[0]}, arg[1]);
        }
        return option;
}

ReserveWorkflow.prototype.system_available = function(arg) {
    var distro_value = getElement(this.distro_id).value 
    var arch_value = jQuery('#'+this.arch_id).val() 
    var params = { 'tg_format' : 'json',
                   'tg_random' : new Date().getTime(),
                   'distro_install_name' : distro_value,
                   'arches' : arch_value }
       
    if (arch_value.length > 1) {
        var d = loadJSONDoc('/find_systems_for_multiple_distros?' + queryString(params));
    } else { //If we have multiple arches we need to get our systems another way 
        var d = loadJSONDoc('/find_systems_for_distro?' + queryString(params));
    }


    d.addCallback(this.show_auto_pick_warnings)                
}

ReserveWorkflow.prototype.show_auto_pick_warnings = function(result) {
    count = result['count'] 
    if (count < 1) {
         getElement('reserve_error').setAttribute('style','display:inline') 
    } else {
         location.href='/reserveworkflow/reserve?distro_id=' + result['distro_id']
    }
}

ReserveWorkflow.prototype.get_distros = function() {
    var distro_family_value = getElement(this.distro_family_id).value
    if (!distro_family_value) { //we aren't going to get any distros if we dont have our distro family
        return;
    }
    var arch_value = jQuery('#'+this.arch_id).val()  
    var method_value = getElement(this.method_id).value
    var tag_value = getElement(this.tag_id).value
    var params = { 'tg_format' : 'json',
                   'tg_random' : new Date().getTime(),
                   'arch' : arch_value,
                   'distro_family' : distro_family_value,
                   'method' : method_value,
                   'tag' : tag_value }

    var d = loadJSONDoc('/reserveworkflow/get_distro_options?' + queryString(params)); 
    d.addCallback(this.replaceDistros)
};


ReserveWorkflow.prototype.replaceDistros = function(result) {  
    if (result.options.length > 0) {
        var arch_value = jQuery('#'+this.arch_id).val() 
        if (arch_value.length == 1) {
            getElement(this.submit_id).removeAttribute('disabled')
        } else {
            getElement(this.submit_id).setAttribute('disabled',1)
        }
       
        getElement(this.auto_pick_id).removeAttribute('disabled')
    } else {
        result.options.unshift('None selected')
        getElement(this.submit_id).setAttribute('disabled',1)
        getElement(this.auto_pick_id).setAttribute('disabled',1)
    }

    replaceChildNodes(this.distro_id, map(this.replaceOptions, result.options));
}

ReserveWorkflow.prototype.replaceOptions = function(arg) {
    option = OPTION({"value": arg}, arg)
    return option
}
