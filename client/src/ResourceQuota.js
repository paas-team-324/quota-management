import React from 'react';
import { TextField } from '@material-ui/core';

class ResourceQuota extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            
        };
    };

    inputValidation(regex) {

    }

    render() {

        return (
            <div>
                {Object.keys(this.props.fields).map(field =>
                    <div>
                        <TextField
                            id={field}
                            name={field}
                            label={this.props.fields[field]["name"]}
                            fullWidth
                        />
                    </div>
                )}
            </div>
        )

    }

}

export default ResourceQuota;