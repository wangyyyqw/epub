export namespace main {
	
	export class BackendResult {
	    stdout: string;
	    stderr: string;
	
	    static createFrom(source: any = {}) {
	        return new BackendResult(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.stdout = source["stdout"];
	        this.stderr = source["stderr"];
	    }
	}

}

